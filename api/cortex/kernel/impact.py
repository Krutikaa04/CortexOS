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
) -> dict[int, list[dict]]:
    """Reverse-BFS over dependency edges: artifacts that transitively depend on
    the seeds. hop 1 = direct impact, hop 2 = indirect impact."""
    by_hop: dict[int, list[dict]] = {}
    seen = set(seed_ids)
    frontier = list(seed_ids)
    for hop in range(1, max_hops + 1):
        if not frontier:
            break
        rows = (
            await session.execute(
                text(
                    "SELECT DISTINCT a.id, a.qualified_name, a.kind, a.raw_text, a.facts, "
                    "       a.summary_text, a.raw_token_count, sf.path, e.kind AS edge_kind "
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
            hop_items.append(dict(r._mapping))
        if hop_items:
            by_hop[hop] = hop_items
        frontier = next_frontier
    return by_hop


_PROMPT = """\
You are CortexOS Change Impact Guard reviewing a pull request. Use ONLY the
repository evidence below — never invent files, symbols, or behavior. If the
evidence does not support a claim, omit it.

CHANGED CODE (what the diff modifies):
{changed}

DEPENDENT CODE (what the graph shows relies on the changed code):
{impacted}

Write a concise review with EXACTLY these sections, each on its own line:
PROBLEMS: bullet the concrete risks this change could introduce (semicolon-separated).
TESTS: the specific tests that should run or be added (semicolon-separated).
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


async def run_impact_analysis(
    session: AsyncSession, version_id: uuid.UUID, diff: str
) -> dict:
    """Full Change Impact Guard analysis for one diff. Synchronous: one model
    call at the end; everything before it is deterministic graph work."""
    t0 = time.monotonic()
    changes = parse_unified_diff(diff)
    code_files = [c for c in changes if not c.is_delete]

    changed_arts, resolved_paths = await _resolve_changed_artifacts(session, version_id, code_files)
    seed_ids = [a["id"] for a in changed_arts]

    by_hop = await _blast_radius(session, version_id, seed_ids) if seed_ids else {}
    direct = by_hop.get(1, [])
    indirect = by_hop.get(2, [])

    # sensitivity over every real path/name in play
    sens_texts = [a["path"] + " " + a["qualified_name"] for a in changed_arts + direct + indirect]
    sensitivity = classify_sensitivity(sens_texts) if sens_texts else classify_sensitivity(
        [c.path for c in changes]
    )
    has_inherit = any(d.get("edge_kind") == "inherits" for d in direct)
    level, reasons = score_risk(len(direct), len(indirect), sensitivity, has_inherit)

    # --- reuse the Context Compiler on changed + impacted artifacts ---
    candidates = [_artifact_to_candidate(a, True) for a in changed_arts]
    candidates += [_artifact_to_candidate(a, False) for a in direct + indirect]
    profile = profile_task("change impact analysis")
    profile.context_budget_tokens = 2600
    compiled = compile_context(candidates, profile) if candidates else None

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
    if compiled and compiled.included:
        try:
            result = await get_model_client().generate(
                _PROMPT.format(changed=changed_block, impacted=impacted_block),
                temperature=0.1,
                max_tokens=700,
            )
            narrative_raw = result["text"]
            metrics.update(
                model_calls=1,
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
            )
            problems = _split_items(_section("PROBLEMS", narrative_raw))
            tests = _split_items(_section("TESTS", narrative_raw))
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

    # measured confidence: how much of the changed diff we could ground in the
    # graph, tempered by whether the change is connected to any dependents.
    coverage = len(resolved_paths) / max(1, len(code_files))
    connected = 1.0 if (direct or indirect) else 0.65
    confidence = round(100 * coverage * (0.75 + 0.25 * connected))

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

    return {
        "risk_level": level,
        "risk_reasons": reasons,
        "confidence": confidence,
        "sensitivity": sensitivity,
        "changed_files": [c.path for c in changes],
        "changed_artifacts": _slim(changed_arts, "changed"),
        "direct_impact": _slim(direct, "direct"),
        "indirect_impact": _slim(indirect, "indirect"),
        "problems": problems,
        "recommended_tests": tests,
        "suggested_patch": patch,
        "summary": summary,
        "narrative_raw": narrative_raw,
        "metrics": metrics,
        "evidence_grounded": bool(compiled and compiled.included),
    }


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
