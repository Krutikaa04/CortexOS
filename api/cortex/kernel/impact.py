"""Change Impact Guard — CortexOS's flagship engineering-intelligence task.

A pull-request diff is turned into a grounded impact report by reusing the
existing Kernel rather than a new pipeline:

    diff ──parse──▶ changed artifacts ──reverse graph BFS──▶ blast radius
         │                                                        │
         │                            Knowledge Graph (artifact_edge)
         ▼                                                        ▼
    deterministic risk scoring  ◀── sensitivity over real paths ──┘
         │
         ▼
    Context Compiler (changed + impacted artifacts) ─▶ ONE model call ─▶ narrative

The structural work — what a change touches and what transitively depends on
it — is *deterministic graph traversal*, so no inference is spent on it (the
Inference Budget Controller philosophy). Only the human-readable narrative
(problems, tests, patch) costs a single generation. Every number in the
report is measured from that real execution or counted from the graph.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.kernel.compiler import compile_context
from cortex.kernel.profiler import profile_task
from cortex.kernel.retriever import Candidate
from cortex.models_client import ModelUnavailableError, get_model_client

# Edges whose reverse direction means "depends on": if B changes, the A in
# `A --kind--> B` is impacted. 'contains' is structural nesting, not a
# dependency, so it is excluded from blast-radius propagation.
_DEPENDENCY_EDGE_KINDS = ("calls", "imports", "inherits", "references_doc", "documents")

# Concept sensitivity — matched against real file paths + qualified names.
_SENSITIVITY = {
    "authentication": re.compile(r"auth|login|logout|jwt|token|session|credential|oauth|signin", re.I),
    "security": re.compile(r"secur|crypt|sign|verif|hash|hmac|encrypt|decrypt|permission|access|sanitiz", re.I),
    "payments": re.compile(r"payment|billing|charge|invoice|stripe|checkout|refund|price", re.I),
    "database": re.compile(r"\bdb\b|database|sql|query|migration|schema|orm|persist", re.I),
    "configuration": re.compile(r"config|settings|\benv\b|environment", re.I),
    "caching": re.compile(r"cache|redis|memcache|lru", re.I),
}

# Engineering-dimension classification of an affected component (v2). Each
# affected artifact is bucketed by its real path/name so the report reasons
# above the file level. Order matters: first match wins for the primary label.
_DIMENSIONS: list[tuple[str, re.Pattern]] = [
    ("database", re.compile(r"\b(migration|schema|models?|entity|repository|orm|sql|db|database|persist)\b", re.I)),
    ("api", re.compile(r"\b(api|routes?|controller|endpoint|handler|resolver|graphql|urls|views)\b", re.I)),
    ("configuration", re.compile(r"\b(config|settings|env|environment|tsconfig)\b|\.ya?ml\b|package\.json|pyproject", re.I)),
    ("background_worker", re.compile(r"\b(worker|jobs?|tasks?|queue|celery|cron|scheduler|ingest\w*)\b", re.I)),
    ("external_service", re.compile(r"\b(client|http\w*|fetch|requests|stripe|s3|boto|sdk|webhook|integration|smtp|email)\b", re.I)),
    ("frontend", re.compile(r"\.(tsx|jsx)\b|\b(components?|pages?|react|next|hooks?|ui)\b", re.I)),
    ("caching", re.compile(r"\b(cache|redis|memcache|lru)\b", re.I)),
    ("authentication", re.compile(r"\b(auth|login|logout|jwt|token|session|credential|oauth)\b", re.I)),
]

# Human-readable rationale per dimension, used for deterministic follow-ups
# and category reasoning ("why this component appears").
_DIMENSION_REASON = {
    "database": "data layer — verify schema/migration compatibility and query call sites",
    "api": "API boundary — a changed contract can break clients of this route/handler",
    "configuration": "configuration — consumers of these settings may need updating",
    "background_worker": "background processing — job/ingestion behavior may shift",
    "external_service": "external integration — outbound contract or error handling may change",
    "frontend": "frontend surface — component props/rendering may need updating",
    "caching": "caching layer — invalidation or key shape may be affected",
    "authentication": "authentication path — a change here has security consequences",
}


def classify_dimension(path: str, qualified_name: str) -> str:
    """Primary engineering dimension for one component (path + name).

    Underscores/hyphens are normalized to spaces so word-boundary patterns
    match tokens like `stripe_client` or `user-service`."""
    blob = re.sub(r"[_\-]+", " ", f"{path} {qualified_name}")
    for name, pat in _DIMENSIONS:
        if pat.search(blob):
            return name
    return "dependency"


@dataclass
class FileChange:
    path: str
    new_ranges: list[tuple[int, int]] = field(default_factory=list)
    added: int = 0
    removed: int = 0
    is_new: bool = False
    is_delete: bool = False


def parse_unified_diff(diff: str) -> list[FileChange]:
    """Parse a unified/`git diff` into per-file changed line ranges (new side)."""
    files: list[FileChange] = []
    current: FileChange | None = None
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            m = re.search(r"b/(\S+)", line)
            current = FileChange(path=m.group(1) if m else "?")
            files.append(current)
        elif line.startswith("new file mode") and current:
            current.is_new = True
        elif line.startswith("deleted file mode") and current:
            current.is_delete = True
        elif line.startswith("+++ "):
            path = line[4:].strip()
            if path == "/dev/null":
                if current:
                    current.is_delete = True
            else:
                path = re.sub(r"^b/", "", path)
                if current is None or (current.path == "?"):
                    current = current or FileChange(path=path)
                    if current not in files:
                        files.append(current)
                current.path = path
        elif line.startswith("@@") and current:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start = int(m.group(1))
                length = int(m.group(2)) if m.group(2) is not None else 1
                end = start + max(length, 1) - 1
                current.new_ranges.append((start, end))
        elif current and line.startswith("+") and not line.startswith("+++"):
            current.added += 1
        elif current and line.startswith("-") and not line.startswith("---"):
            current.removed += 1
    return [f for f in files if f.path and f.path != "?"]


def _spans_overlap(a_start: int, a_end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(not (a_end < s or a_start > e) for s, e in ranges)


def classify_sensitivity(texts: list[str]) -> list[str]:
    """Concept labels (auth/security/…) matched over real paths + names."""
    blob = " ".join(texts)
    return [concept for concept, pat in _SENSITIVITY.items() if pat.search(blob)]


def score_risk(
    direct: int, indirect: int, sensitivity: list[str], has_inherit: bool
) -> tuple[str, list[str]]:
    """Deterministic risk level from measured structural signals."""
    blast = direct + indirect
    reasons: list[str] = []
    critical = any(s in ("authentication", "security", "payments") for s in sensitivity)

    if critical:
        reasons.append(f"touches sensitive area: {', '.join(sensitivity)}")
    if has_inherit:
        reasons.append("changes a base class other code inherits from")
    if direct:
        reasons.append(f"{direct} direct dependent(s)")
    if indirect:
        reasons.append(f"{indirect} indirect dependent(s)")

    if critical or blast >= 15 or direct >= 8 or has_inherit and direct >= 3:
        level = "HIGH"
    elif blast >= 5 or direct >= 3 or sensitivity:
        level = "MEDIUM"
    else:
        level = "LOW"
    if not reasons:
        reasons.append("no dependents found in the graph for the changed code")
    return level, reasons


# ------------------------------------------------------------------ DB layer


async def _resolve_changed_artifacts(
    session: AsyncSession, version_id: uuid.UUID, changes: list[FileChange]
) -> tuple[list[dict], set[str]]:
    """Map changed lines to the semantic artifacts they fall inside.

    Returns (artifacts, resolved_paths). An artifact is 'changed' if it lives
    in a changed file and its span overlaps a changed line range (or the file
    is new/whole-file changed).
    """
    resolved: list[dict] = []
    resolved_paths: set[str] = set()
    for change in changes:
        rows = (
            await session.execute(
                text(
                    "SELECT a.id, a.qualified_name, a.kind, a.raw_text, a.facts, "
                    "       a.summary_text, a.raw_token_count, a.span_start_line, "
                    "       a.span_end_line, sf.path "
                    "FROM semantic_artifact a JOIN source_file sf ON sf.id = a.source_file_id "
                    "WHERE a.source_version_id = :vid AND sf.path = :path"
                ),
                {"vid": version_id, "path": change.path},
            )
        ).all()
        if not rows:
            continue
        whole_file = change.is_new or not change.new_ranges
        for r in rows:
            if whole_file or _spans_overlap(r.span_start_line, r.span_end_line, change.new_ranges):
                resolved.append(dict(r._mapping))
                resolved_paths.add(change.path)
    return resolved, resolved_paths


async def _blast_radius(
    session: AsyncSession, version_id: uuid.UUID, seed_ids: list[uuid.UUID], max_hops: int = 2
) -> tuple[dict[int, list[dict]], dict]:
    """Reverse-BFS over dependency edges: artifacts that transitively depend on
    the seeds. hop 1 = direct impact, hop 2 = indirect impact.

    Also returns a predecessor map {node_id: (via_id, edge_kind, confidence)} so
    the caller can reconstruct the dependency chain (evidence) from any impacted
    node back to a changed seed — the report never lists a file without the
    reason it is affected."""
    by_hop: dict[int, list[dict]] = {}
    parents: dict = {}
    seen = set(seed_ids)
    frontier = list(seed_ids)
    for hop in range(1, max_hops + 1):
        if not frontier:
            break
        rows = (
            await session.execute(
                text(
                    "SELECT DISTINCT a.id, a.qualified_name, a.kind, a.raw_text, a.facts, "
                    "       a.summary_text, a.raw_token_count, sf.path, "
                    "       e.kind AS edge_kind, e.to_artifact_id AS via_id, e.confidence "
                    "FROM artifact_edge e "
                    "JOIN semantic_artifact a ON a.id = e.from_artifact_id "
                    "JOIN source_file sf ON sf.id = a.source_file_id "
                    "WHERE e.source_version_id = :vid "
                    "  AND e.to_artifact_id = ANY(:frontier) "
                    "  AND e.kind = ANY(:kinds)"
                ),
                {"vid": version_id, "frontier": frontier, "kinds": list(_DEPENDENCY_EDGE_KINDS)},
            )
        ).all()
        hop_items: list[dict] = []
        next_frontier: list[uuid.UUID] = []
        for r in rows:
            if r.id in seen:
                continue
            seen.add(r.id)
            next_frontier.append(r.id)
            parents[r.id] = (r.via_id, r.edge_kind, float(r.confidence or 1.0))
            hop_items.append(dict(r._mapping))
        if hop_items:
            by_hop[hop] = hop_items
        frontier = next_frontier
    return by_hop, parents


_PROMPT = """\
You are CortexOS Change Impact Guard reviewing a pull request. Use ONLY the
repository evidence below — never invent files, symbols, or behavior. If the
evidence does not support a claim, omit it.

CHANGED CODE (what the diff modifies):
{changed}

DEPENDENT CODE (what the graph shows relies on the changed code):
{impacted}

Write a concise Staff-engineer review with EXACTLY these sections, each on its
own line:
PROBLEMS: concrete risks this change could introduce, each tied to the evidence (semicolon-separated).
ARCHITECTURE: the architectural/layer consequences (which boundaries, services or shared code are affected), else "none".
TESTS: specific tests to run or add, each naming the component it protects (semicolon-separated).
FOLLOWUPS: likely follow-up changes (update interface/route/config/schema/tests, handle null path…), NOT full code (semicolon-separated).
PATCH: a short fenced code block with a defensive fix or guard if warranted, else "none".
SUMMARY: one sentence on why this change is or isn't risky.
"""


def _artifact_to_candidate(a: dict, changed: bool) -> Candidate:
    return Candidate(
        artifact_id=a["id"],
        qualified_name=a["qualified_name"],
        kind=a["kind"],
        path=a["path"],
        raw_text=a["raw_text"],
        facts=a.get("facts"),
        summary_text=a.get("summary_text"),
        raw_token_count=a["raw_token_count"],
        # changed artifacts are the subject (get richer representation);
        # impacted artifacts are graph context (compiled down to facts).
        score=0.95 if changed else 0.5,
        requirements={"change"} if changed else set(),
        provenance=["changed" if changed else "impacted"],
    )


def _section(name: str, textblob: str) -> str:
    m = re.search(rf"{name}:\s*(.*?)(?=\n[A-Z]+:|\Z)", textblob, re.S | re.I)
    return m.group(1).strip() if m else ""


def _split_items(blob: str) -> list[str]:
    parts = re.split(r";|\n[-*]\s*|\n\d+[.)]\s*", blob)
    return [p.strip(" -*\n") for p in parts if p.strip(" -*\n") and len(p.strip()) > 2]


# ------------------------------------------------------- v2 reasoning helpers


def _sym(qn: str) -> str:
    return qn.split("::")[-1]


def _build_chains(
    changed: list[dict], direct: list[dict], indirect: list[dict], parents: dict
) -> list[dict]:
    """Reconstruct 'why affected' dependency chains from each impacted node back
    to a changed seed — the report's structural evidence.

    Each chain: impacted --edge--> ... --> changed, rendered as a readable path
    with the exact edge kinds that connect them."""
    seed_ids = {a["id"] for a in changed}
    info = {a["id"]: (_sym(a["qualified_name"]), a["path"]) for a in changed + direct + indirect}
    chains: list[dict] = []
    for node in direct + indirect:
        steps = [info[node["id"]][0]]
        edges: list[str] = []
        cur = node["id"]
        for _ in range(4):  # bounded walk
            parent = parents.get(cur)
            if parent is None:
                break
            via_id, edge_kind, _conf = parent
            edges.append(edge_kind)
            steps.append(info.get(via_id, ("?", ""))[0])
            if via_id in seed_ids:
                break
            cur = via_id
        # "AuthService.login --calls--> verify (changed)"
        rendered = steps[0]
        for i, ek in enumerate(edges):
            rendered += f" --{ek}--> {steps[i + 1]}"
        chains.append({
            "target": info[node["id"]][0],
            "path": info[node["id"]][1],
            "edge_kind": parents.get(node["id"], (None, None, 1.0))[1],
            "chain": rendered,
            "why": f"{info[node['id']][0]} {parents.get(node['id'], (None,'depends on',1.0))[1]} "
                   f"changed code",
        })
    return chains


def _categorize(changed: list[dict], direct: list[dict], indirect: list[dict]) -> dict:
    """Bucket every affected component by engineering dimension, each with the
    reason it appears — reasoning above the file level (v2)."""
    dims: dict[str, list[dict]] = {}
    def _add(items: list[dict], hop: str) -> None:
        for a in items:
            dim = classify_dimension(a["path"], a["qualified_name"])
            if a.get("edge_kind") == "inherits":
                dim = "architectural"
            entry = {
                "symbol": _sym(a["qualified_name"]),
                "path": a["path"],
                "hop": hop,
                "edge_kind": a.get("edge_kind"),
                "reason": _DIMENSION_REASON.get(dim, "depends on the changed code"),
            }
            dims.setdefault(dim, []).append(entry)
    _add(changed, "changed")
    _add(direct, "direct")
    _add(indirect, "indirect")
    return dims


def _confidence(
    resolved_paths: set[str], code_files: list, direct: list[dict], indirect: list[dict],
    parents: dict, has_inherit: bool, dimensions: dict,
) -> dict:
    """Structured confidence: a score plus the concrete signals behind it.

    Replaces a bare percentage — every factor is a measured graph fact."""
    coverage = len(resolved_paths) / max(1, len(code_files))
    edge_kinds = {ek for (_v, ek, _c) in parents.values()}
    factors: list[dict] = []

    factors.append({
        "signal": "diff grounded in graph",
        "detail": f"{len(resolved_paths)}/{len(code_files)} changed file(s) resolved to artifacts",
        "effect": "raises" if coverage >= 0.99 else ("neutral" if coverage >= 0.5 else "lowers"),
    })
    if direct:
        factors.append({"signal": "direct dependency confirmed",
                        "detail": f"{len(direct)} artifact(s) depend directly on the change",
                        "effect": "raises"})
    if "calls" in edge_kinds:
        factors.append({"signal": "call graph verified",
                        "detail": "impact traced through resolved call edges", "effect": "raises"})
    if "imports" in edge_kinds:
        factors.append({"signal": "symbol/import references resolved",
                        "detail": "impact traced through resolved import edges", "effect": "raises"})
    if has_inherit:
        factors.append({"signal": "inheritance detected",
                        "detail": "a changed base class has subclasses", "effect": "raises"})
    if "configuration" in dimensions:
        factors.append({"signal": "configuration relationship detected",
                        "detail": "config consumers are in the blast radius", "effect": "raises"})
    if not (direct or indirect):
        factors.append({"signal": "no dependents found",
                        "detail": "no graph edges point at the changed code",
                        "effect": "lowers"})
    if coverage < 1.0:
        factors.append({"signal": "partial resolution",
                        "detail": "some changed files are not in the graph (new/untracked)",
                        "effect": "lowers"})

    connected = 1.0 if (direct or indirect) else 0.65
    score = round(100 * coverage * (0.75 + 0.25 * connected))
    level = "High" if score >= 80 else "Medium" if score >= 55 else "Low"
    return {"score": score, "level": level, "factors": factors}


def _follow_ups(dimensions: dict, sensitivity: list[str], has_inherit: bool) -> list[dict]:
    """Repository-aware follow-up actions implied by the affected dimensions —
    what to change next, not generated code (v2)."""
    ups: list[dict] = []
    def _add(action: str, why: str) -> None:
        ups.append({"action": action, "why": why})

    if "api" in dimensions:
        _add("Review affected API routes/handlers for contract changes",
             "an API boundary is in the blast radius")
    if "database" in dimensions:
        _add("Verify schema/migration compatibility and update ORM models",
             "the data layer is affected")
    if "configuration" in dimensions:
        _add("Update configuration/env consumers and defaults",
             "configuration is in the blast radius")
    if "frontend" in dimensions:
        _add("Update affected components/props and their UI tests",
             "a frontend surface depends on the change")
    if "background_worker" in dimensions:
        _add("Re-check job/ingestion behavior and idempotency",
             "background processing is affected")
    if "external_service" in dimensions:
        _add("Confirm outbound contract and error/retry handling",
             "an external integration is affected")
    if has_inherit or "architectural" in dimensions:
        _add("Update subclasses/implementations of the changed base",
             "inheritance/architectural relationships are affected")
    if any(s in ("authentication", "security") for s in sensitivity):
        _add("Add security-focused tests around the auth/security path",
             "the change touches a sensitive area")
    return ups


_RISK_ORDINAL = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _compare_revisions(prior: dict, current: dict) -> dict:
    """Diff this analysis against the previous analysis of the same PR (v2).

    Makes review evolution visible: new vs. resolved risks, blast-radius delta,
    and the risk trend."""
    prior_probs = {p.strip().lower() for p in prior.get("problems", [])}
    cur_probs = {p.strip().lower() for p in current.get("problems", [])}
    new_risks = [p for p in current.get("problems", []) if p.strip().lower() not in prior_probs]
    resolved = [p for p in prior.get("problems", []) if p.strip().lower() not in cur_probs]

    def _blast(r: dict) -> int:
        return len(r.get("direct_impact", [])) + len(r.get("indirect_impact", []))

    prior_blast, cur_blast = _blast(prior), _blast(current)
    prior_level = prior.get("risk_level", "LOW")
    cur_level = current.get("risk_level", "LOW")
    delta = _RISK_ORDINAL.get(cur_level, 0) - _RISK_ORDINAL.get(prior_level, 0)
    trend = "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged"
    cur_conf = current.get("confidence", 0)
    prior_conf = prior.get("confidence", 0)
    return {
        "previous_risk_level": prior_level,
        "current_risk_level": cur_level,
        "risk_trend": trend,
        "new_risks": new_risks,
        "resolved_risks": resolved,
        "blast_radius_delta": cur_blast - prior_blast,
        "previous_blast_radius": prior_blast,
        "current_blast_radius": cur_blast,
        "confidence_delta": cur_conf - prior_conf,
    }


async def run_impact_analysis(
    session: AsyncSession, version_id: uuid.UUID, diff: str, emitter=None,
    prior_report: dict | None = None,
) -> dict:
    """Full Change Impact Guard analysis for one diff. The structural phases
    are deterministic graph work; only the final narrative costs one model
    call. When an ``emitter`` is given, each phase is streamed as an event so
    Studio can show real progress instead of a heuristic timer."""

    async def _emit(event_type: str, payload: dict) -> None:
        if emitter is not None:
            await emitter.emit(event_type, payload)

    t0 = time.monotonic()
    await _emit("IMPACT_STARTED", {})
    changes = parse_unified_diff(diff)
    code_files = [c for c in changes if not c.is_delete]
    await _emit("IMPACT_DIFF_PARSED", {"files": [c.path for c in changes], "count": len(changes)})

    changed_arts, resolved_paths = await _resolve_changed_artifacts(session, version_id, code_files)
    seed_ids = [a["id"] for a in changed_arts]
    await _emit(
        "IMPACT_ARTIFACTS_RESOLVED",
        {"changed": [a["qualified_name"].split("::")[-1] for a in changed_arts],
         "count": len(changed_arts)},
    )

    if seed_ids:
        by_hop, parents = await _blast_radius(session, version_id, seed_ids)
    else:
        by_hop, parents = {}, {}
    direct = by_hop.get(1, [])
    indirect = by_hop.get(2, [])
    await _emit("IMPACT_BLAST_RADIUS", {"direct": len(direct), "indirect": len(indirect)})

    # sensitivity over every real path/name in play
    sens_texts = [a["path"] + " " + a["qualified_name"] for a in changed_arts + direct + indirect]
    sensitivity = classify_sensitivity(sens_texts) if sens_texts else classify_sensitivity(
        [c.path for c in changes]
    )
    has_inherit = any(d.get("edge_kind") == "inherits" for d in direct)
    level, reasons = score_risk(len(direct), len(indirect), sensitivity, has_inherit)
    await _emit("IMPACT_RISK_SCORED", {"risk_level": level, "sensitivity": sensitivity})

    # --- reuse the Context Compiler on changed + impacted artifacts ---
    candidates = [_artifact_to_candidate(a, True) for a in changed_arts]
    candidates += [_artifact_to_candidate(a, False) for a in direct + indirect]
    profile = profile_task("change impact analysis")
    profile.context_budget_tokens = 2600
    compiled = compile_context(candidates, profile) if candidates else None
    if compiled:
        await _emit(
            "IMPACT_EVIDENCE_COMPILED",
            {"candidate_tokens": compiled.candidate_tokens,
             "context_tokens_sent": compiled.total_tokens},
        )

    changed_block = _render(compiled, "changed") if compiled else "(no changed code resolved in the graph)"
    impacted_block = _render(compiled, "impacted") if compiled else "(no dependents found)"

    # --- ONE model call for the human-readable narrative ---
    metrics: dict = {
        "model_calls": 0,
        "embedding_calls": 0,
        "candidate_tokens": compiled.candidate_tokens if compiled else 0,
        "context_tokens_sent": compiled.total_tokens if compiled else 0,
    }
    narrative_raw = ""
    problems: list[str] = []
    tests: list[str] = []
    patch = ""
    summary = ""
    architecture_note = ""
    model_followups: list[str] = []
    if compiled and compiled.included:
        await _emit("IMPACT_NARRATIVE", {"status": "generating"})
        try:
            result = await get_model_client().generate(
                _PROMPT.format(changed=changed_block, impacted=impacted_block),
                temperature=0.1,
                max_tokens=800,
            )
            narrative_raw = result["text"]
            metrics.update(
                model_calls=1,
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
            )
            problems = _split_items(_section("PROBLEMS", narrative_raw))
            tests = _split_items(_section("TESTS", narrative_raw))
            model_followups = _split_items(_section("FOLLOWUPS", narrative_raw))
            arch_sec = _section("ARCHITECTURE", narrative_raw)
            architecture_note = "" if arch_sec.lower().startswith("none") else arch_sec
            patch_sec = _section("PATCH", narrative_raw)
            patch = "" if patch_sec.lower().startswith("none") else patch_sec
            summary = _section("SUMMARY", narrative_raw)
        except ModelUnavailableError:
            summary = "Model unavailable — structural impact computed, narrative skipped."

    if compiled and compiled.candidate_tokens:
        metrics["context_reduction_pct"] = round(
            100 * (1 - compiled.total_tokens / compiled.candidate_tokens), 1
        )
    metrics["total_ms"] = int((time.monotonic() - t0) * 1000)

    # --- v2 deterministic reasoning (no extra model calls) ---
    dimensions = _categorize(changed_arts, direct, indirect)
    chains = _build_chains(changed_arts, direct, indirect, parents)
    confidence_explanation = _confidence(
        resolved_paths, code_files, direct, indirect, parents, has_inherit, dimensions
    )
    confidence = confidence_explanation["score"]
    # follow-ups: deterministic (from dimensions) first, then de-duplicated
    # model suggestions that add genuinely new actions.
    follow_ups = _follow_ups(dimensions, sensitivity, has_inherit)
    _seen_fu = {f["action"].lower()[:40] for f in follow_ups}
    for mf in model_followups:
        if mf.lower()[:40] not in _seen_fu:
            follow_ups.append({"action": mf, "why": "suggested from the changed/dependent code"})

    def _slim(items: list[dict], hop: str) -> list[dict]:
        seen: set[str] = set()
        out = []
        for a in items:
            if a["qualified_name"] in seen:
                continue
            seen.add(a["qualified_name"])
            out.append({
                "qualified_name": a["qualified_name"],
                "symbol": a["qualified_name"].split("::")[-1],
                "path": a["path"],
                "kind": a["kind"],
                "edge_kind": a.get("edge_kind"),
                "hop": hop,
            })
        return out

    report = {
        "risk_level": level,
        "risk_reasons": reasons,
        "confidence": confidence,
        "confidence_explanation": confidence_explanation,
        "sensitivity": sensitivity,
        "changed_files": [c.path for c in changes],
        "changed_artifacts": _slim(changed_arts, "changed"),
        "direct_impact": _slim(direct, "direct"),
        "indirect_impact": _slim(indirect, "indirect"),
        "impact_dimensions": dimensions,
        "dependency_chains": chains,
        "architecture_note": architecture_note,
        "problems": problems,
        "recommended_tests": tests,
        "follow_ups": follow_ups,
        "suggested_patch": patch,
        "summary": summary,
        "narrative_raw": narrative_raw,
        "metrics": metrics,
        "evidence_grounded": bool(compiled and compiled.included),
    }

    # --- v2 revision comparison: diff against the prior analysis of this PR ---
    if prior_report:
        report["revision_comparison"] = _compare_revisions(prior_report, report)

    await _emit("IMPACT_COMPLETED", {"risk_level": level, "confidence": confidence})
    return report


def _render(compiled, which: str) -> str:
    """Render only the changed or only the impacted artifacts from a compiled
    context (provenance distinguishes them)."""
    blocks = []
    for item in compiled.included:
        is_changed = "changed" in item.candidate.provenance
        if (which == "changed") != is_changed:
            continue
        header = f"[{item.candidate.path} :: {item.candidate.qualified_name.split('::')[-1]}]"
        blocks.append(f"{header}\n{item.text}")
    return "\n\n".join(blocks) or "(none)"
