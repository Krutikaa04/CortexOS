"""Sufficiency Evaluator.

Decides whether the produced answer is adequate or the context must be
expanded. Deliberately does NOT trust model self-confidence alone —
signals are cheap, observable heuristics:

  - the answer explicitly admits missing context,
  - the answer is empty / degenerate,
  - requirement coverage of the compiled context was too low.

If insufficient, the kernel expands (higher budget, more candidates) and
retries once. Escalation beyond one expansion is V2 scope.
"""

import re
from dataclasses import dataclass

from cortex.kernel.compiler import CompiledContext
from cortex.kernel.requirements import Requirement

_INSUFFICIENT_MARKERS = re.compile(
    r"(context does not|context doesn't|no information|not enough information|"
    r"cannot determine|can't determine|not specified|not mentioned|"
    r"insufficient context|unable to answer)",
    re.IGNORECASE,
)

MIN_ANSWER_CHARS = 8
MIN_REQUIREMENT_COVERAGE = 0.5


@dataclass
class SufficiencyResult:
    sufficient: bool
    reasons: list[str]
    requirement_coverage: float

    def as_dict(self) -> dict:
        return {
            "sufficient": self.sufficient,
            "reasons": self.reasons,
            "requirement_coverage": round(self.requirement_coverage, 2),
        }


def evaluate_sufficiency(
    answer: str,
    requirements: list[Requirement],
    context: CompiledContext,
    extra_covered: set[str] = frozenset(),
) -> SufficiencyResult:
    """`extra_covered`: requirement ids already served outside the compiled
    context — e.g. by SVM-resident pages in session mode."""
    reasons: list[str] = []

    covered = set(extra_covered)
    for item in context.included:
        covered |= item.candidate.requirements
    coverage = len(covered) / len(requirements) if requirements else 1.0

    if len(answer.strip()) < MIN_ANSWER_CHARS:
        reasons.append("answer_empty")
    if _INSUFFICIENT_MARKERS.search(answer):
        reasons.append("answer_admits_missing_context")
    if coverage < MIN_REQUIREMENT_COVERAGE:
        reasons.append(f"low_requirement_coverage:{coverage:.2f}")

    return SufficiencyResult(
        sufficient=not reasons,
        reasons=reasons,
        requirement_coverage=coverage,
    )
