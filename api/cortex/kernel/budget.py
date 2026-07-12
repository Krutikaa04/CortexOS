"""Inference Budget Controller.

Before any optional, expensive operation the kernel asks the budget
controller a single question: *should this inference happen, or can a
cheaper deterministic path produce an equivalent result?* Every answer is
a typed, recorded ``BudgetDecision`` so the full cost of a pipeline run —
which model calls were spent and which were deliberately skipped — is
auditable after the fact.

This is the deterministic core of CortexOS's inference-optimization
contribution. The controlling rule: **no LLM call ever decides whether to
make an LLM call.** Routing is a pure function of the task profile, so the
same question always takes the same path and the decision is measurable.
"""

from dataclasses import dataclass

from cortex.kernel.profiler import TaskProfile

# The one task type that provably does not benefit from model-based
# requirement decomposition: a single-fact lookup. Keeping this as data
# (not a scattered ``== "factual"`` check) means the fast-path boundary
# lives in exactly one place.
_FAST_PATH_TASK_TYPES = frozenset({"factual"})


@dataclass
class BudgetDecision:
    """One recorded answer to 'should this operation happen?'."""

    operation: str          # e.g. "requirement_generation", "context_expansion"
    decision: str           # "SKIP" | "EXECUTE" | "ESCALATE"
    reason: str             # human-readable justification, always present

    def as_dict(self) -> dict[str, str]:
        return {"operation": self.operation, "decision": self.decision, "reason": self.reason}


class InferenceBudgetController:
    """Deterministic gatekeeper for a single execution's optional inference.

    Construct once per execution from the task profile, then ask it before
    each expensive step. It records every decision it makes; read them back
    from :attr:`decisions` for the execution's metrics block.
    """

    def __init__(self, profile: TaskProfile) -> None:
        self.profile = profile
        self.decisions: list[BudgetDecision] = []

    # -- routing (pure function of the profile) --------------------------

    @property
    def fast_path(self) -> bool:
        """True when the question is a simple factual lookup.

        Fast path skips the requirement-decomposition LLM call (measured at
        11-43s per question on local CPU); heuristic requirements retrieve
        just as well for single-fact lookups.
        """
        return self.profile.task_type in _FAST_PATH_TASK_TYPES

    @property
    def path(self) -> str:
        return "fast" if self.fast_path else "deep"

    # -- per-operation gates (record then return the decision) -----------

    def decide_requirement_generation(self) -> BudgetDecision:
        """Should the requirement-decomposition model call happen?"""
        if self.fast_path:
            decision = BudgetDecision(
                "requirement_generation",
                "SKIP",
                "fast path: factual question, heuristic requirements suffice",
            )
        else:
            decision = BudgetDecision(
                "requirement_generation",
                "EXECUTE",
                f"{self.profile.task_type} question needs model decomposition",
            )
        self.decisions.append(decision)
        return decision

    def decide_expansion(
        self,
        *,
        sufficient: bool,
        round_no: int,
        max_rounds: int,
        reasons: list[str],
    ) -> BudgetDecision:
        """After a sufficiency check, should the kernel spend another round?

        Escalation costs a second retrieval + compile + generation, so it is
        only taken when the deterministic sufficiency evaluator reports the
        answer is not yet grounded *and* rounds remain.
        """
        if sufficient:
            decision = BudgetDecision(
                "context_expansion", "SKIP", "deterministic sufficiency passed"
            )
        elif round_no >= max_rounds:
            decision = BudgetDecision(
                "context_expansion", "SKIP", "round limit reached"
            )
        else:
            decision = BudgetDecision(
                "context_expansion", "ESCALATE", "; ".join(reasons)
            )
        self.decisions.append(decision)
        return decision
