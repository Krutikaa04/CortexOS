"""Context Compiler — CortexOS's signature execution component.

Conventional RAG pastes retrieved chunks into the prompt. The compiler
instead treats retrieved knowledge as candidate material and produces the
minimum sufficient representation:

  1. necessity scoring   value per token, requirement-aware
  2. redundancy removal  containment + high lexical overlap
  3. representation selection
       cheapest level that can serve the requirement:
       facts/signature (L1) -> summary (L3) -> raw source (L4/L5)
  4. token packing       greedy by value density under the profiler budget

Every exclusion carries a reason — the Context X-Ray view depends on
being able to explain every decision.
"""

import logging
from dataclasses import dataclass

from cortex.kernel.profiler import TaskProfile
from cortex.kernel.retriever import Candidate
from cortex.tokens import estimate_tokens

log = logging.getLogger("cortex.kernel.compiler")

MIN_SCORE = 0.05          # below this, not worth considering at all
OVERLAP_THRESHOLD = 0.75  # token-set overlap treated as duplicate
# A candidate serving requirements directly earns full representation;
# graph-only context is compressed to facts by default.
RAW_TEXT_TOP_N = 4        # max artifacts included as raw source


@dataclass
class CompiledArtifact:
    candidate: Candidate
    representation: str  # 'facts' | 'summary' | 'raw'
    text: str
    token_count: int
    value_density: float


@dataclass
class Rejection:
    qualified_name: str
    reason: str
    tokens_saved: int
    detail: str = ""


@dataclass
class CompiledContext:
    included: list[CompiledArtifact]
    rejected: list[Rejection]
    total_tokens: int
    candidate_tokens: int  # what a naive "send everything retrieved" would cost

    def render(self) -> str:
        blocks = []
        for item in self.included:
            header = f"[{item.candidate.path} :: {item.candidate.qualified_name.split('::')[-1]}]"
            blocks.append(f"{header}\n{item.text}")
        return "\n\n".join(blocks)


def compile_context(
    candidates: list[Candidate],
    profile: TaskProfile,
) -> CompiledContext:
    budget = profile.context_budget_tokens
    candidate_tokens = sum(c.raw_token_count for c in candidates)
    rejected: list[Rejection] = []
    survivors: list[Candidate] = []

    # --- 1. necessity filter ---
    for c in candidates:
        if c.score < MIN_SCORE:
            rejected.append(Rejection(c.qualified_name, "low_necessity", c.raw_token_count,
                                      f"score={c.score:.3f}"))
        else:
            survivors.append(c)

    # --- 2. redundancy: containment (a module artifact contains its own
    #        functions' text) and near-duplicate text overlap ---
    survivors.sort(key=lambda c: c.score, reverse=True)
    kept: list[Candidate] = []
    for c in survivors:
        duplicate_of = _find_redundant(c, kept)
        if duplicate_of is not None:
            rejected.append(Rejection(c.qualified_name, "duplicate", c.raw_token_count,
                                      f"covered by {duplicate_of}"))
        else:
            kept.append(c)

    # --- 3+4. representation selection under greedy budget packing ---
    included: list[CompiledArtifact] = []
    used_tokens = 0
    raw_used = 0
    for c in kept:
        serves_requirement = bool(c.requirements)
        options = _representation_options(c, serves_requirement, raw_used < RAW_TEXT_TOP_N)
        placed = False
        for representation, text_ in options:
            tokens = estimate_tokens(text_)
            if used_tokens + tokens <= budget:
                density = c.score / max(tokens, 1)
                included.append(CompiledArtifact(c, representation, text_, tokens, density))
                used_tokens += tokens
                if representation == "raw":
                    raw_used += 1
                placed = True
                break
        if not placed:
            rejected.append(Rejection(c.qualified_name, "budget_exceeded", c.raw_token_count,
                                      f"budget={budget}, used={used_tokens}"))

    log.info(
        "compiled context: %d included (%d tokens), %d rejected, candidates=%d tokens",
        len(included), used_tokens, len(rejected), candidate_tokens,
    )
    return CompiledContext(
        included=included,
        rejected=rejected,
        total_tokens=used_tokens,
        candidate_tokens=candidate_tokens,
    )


def _find_redundant(c: Candidate, kept: list[Candidate]) -> str | None:
    """Return the qualified name that makes `c` redundant, or None."""
    for k in kept:
        # Structural containment: same file, span covered by an already-kept
        # artifact (e.g. module kept, its method offered next — or vice versa).
        if c.qualified_name.startswith(f"{k.qualified_name}.") or (
            "::" in c.qualified_name
            and k.qualified_name == c.qualified_name.split("::", 1)[0]
        ):
            return k.qualified_name
        if _token_overlap(c.raw_text, k.raw_text) >= OVERLAP_THRESHOLD:
            return k.qualified_name
    return None


def _token_overlap(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def _representation_options(
    c: Candidate, serves_requirement: bool, raw_allowed: bool
) -> list[tuple[str, str]]:
    """Representation ladder for one candidate, cheapest acceptable first.

    Requirement-serving artifacts try the RICHEST representation first
    (raw source), then degrade to fit budget. Graph-context artifacts try
    the CHEAPEST first (facts) — they support reasoning, they are not the
    subject of the answer.
    """
    facts_text = _facts_text(c)
    options: list[tuple[str, str]] = []

    if serves_requirement:
        if raw_allowed:
            options.append(("raw", c.raw_text))
        if c.summary_text:
            options.append(("summary", c.summary_text))
        if facts_text:
            options.append(("facts", facts_text))
        if not options:
            options.append(("raw", c.raw_text))
    else:
        if facts_text:
            options.append(("facts", facts_text))
        if c.summary_text:
            options.append(("summary", c.summary_text))
        # last resort: truncated raw
        options.append(("raw", c.raw_text[:1200]))
    return options


def _facts_text(c: Candidate) -> str:
    if not c.facts:
        return ""
    lines = []
    for fact in c.facts:
        if fact.get("type") == "signature":
            lines.append(fact["value"])
        elif fact.get("type") == "constant":
            lines.append(f"{fact['name']} = {fact['value']}")
        elif fact.get("type") == "fact":
            lines.append(f"{fact['subject']} {fact['predicate']} {fact['object']}")
    doc = (c.raw_text.splitlines() or [""])[0] if not lines else ""
    return "\n".join(filter(None, [*lines, doc]))
