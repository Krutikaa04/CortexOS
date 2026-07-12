import uuid

from cortex.kernel.compiler import CompiledContext, compile_context
from cortex.kernel.profiler import profile_task
from cortex.kernel.requirements import Requirement, _heuristic_requirements
from cortex.kernel.retriever import Candidate
from cortex.kernel.sufficiency import evaluate_sufficiency


def make_candidate(qn: str, score: float, text: str, *, kind: str = "function",
                   requirements: set[str] | None = None, facts: list | None = None) -> Candidate:
    return Candidate(
        artifact_id=uuid.uuid4(),
        qualified_name=qn,
        kind=kind,
        path=qn.split("::")[0],
        raw_text=text,
        facts=facts,
        summary_text=None,
        raw_token_count=max(1, len(text) // 4),
        score=score,
        requirements=requirements or set(),
        provenance=["test"],
    )


# ---------------------------------------------------------------- profiler


def test_profiler_budgets_scale_with_task_type():
    factual = profile_task("What is the token TTL?")
    multi = profile_task("Will changing the AuthService schema break payment_routes?")
    assert factual.task_type == "factual"
    assert multi.task_type == "multi_hop"
    assert multi.context_budget_tokens > factual.context_budget_tokens
    assert multi.dependency_depth > factual.dependency_depth


# ---------------------------------------------------------------- compiler


def test_compiler_rejects_low_necessity():
    profile = profile_task("What is X?")
    good = make_candidate("a.py::good", 0.9, "def good(): pass", requirements={"r1"})
    noise = make_candidate("b.py::noise", 0.01, "def noise(): pass")
    ctx = compile_context([good, noise], profile)
    assert any(r.reason == "low_necessity" and r.qualified_name == "b.py::noise"
               for r in ctx.rejected)
    assert [i.candidate.qualified_name for i in ctx.included] == ["a.py::good"]


def test_compiler_removes_contained_duplicates():
    profile = profile_task("What is X?")
    cls = make_candidate("a.py::AuthService", 0.9, "class AuthService:\n    def verify(self): ...",
                         kind="class", requirements={"r1"})
    method = make_candidate("a.py::AuthService.verify", 0.8, "def verify(self): ...",
                            requirements={"r1"})
    ctx = compile_context([cls, method], profile)
    assert len(ctx.included) == 1
    assert ctx.rejected[0].reason == "duplicate"


def test_compiler_respects_budget():
    profile = profile_task("What is X?")
    profile.context_budget_tokens = 50
    big1 = make_candidate("a.py::f1", 0.9, "x " * 400, requirements={"r1"})
    big2 = make_candidate("b.py::f2", 0.8, "y " * 400, requirements={"r1"})
    ctx = compile_context([big1, big2], profile)
    assert ctx.total_tokens <= 50 or len(ctx.included) <= 1
    assert any(r.reason == "budget_exceeded" for r in ctx.rejected) or len(ctx.included) < 2


def test_compiler_uses_facts_for_graph_context():
    profile = profile_task("What is X?")
    direct = make_candidate("a.py::hit", 0.9, "def hit(): pass", requirements={"r1"})
    graph_only = make_candidate(
        "b.py::neighbor", 0.4, "def neighbor(): pass\n" * 30,
        facts=[{"type": "signature", "value": "def neighbor()"}],
    )
    ctx = compile_context([direct, graph_only], profile)
    reprs = {i.candidate.qualified_name: i.representation for i in ctx.included}
    assert reprs.get("b.py::neighbor") == "facts"


def test_compiler_reports_reduction():
    profile = profile_task("What is X?")
    candidates = [
        make_candidate(f"m{i}.py::f{i}", 0.5 - i * 0.01, f"def f{i}(): pass\n" * 20,
                       requirements={"r1"} if i < 3 else set())
        for i in range(20)
    ]
    ctx = compile_context(candidates, profile)
    assert ctx.candidate_tokens > ctx.total_tokens > 0


# ------------------------------------------------------------- sufficiency


def _ctx_with_coverage(reqs: list[Requirement], covered: set[str]) -> CompiledContext:
    included = [
        # one artifact that claims to serve the covered requirements
        type("I", (), {"candidate": make_candidate("a.py::x", 0.9, "text",
                                                   requirements=covered)})()
    ]
    return CompiledContext(included=included, rejected=[], total_tokens=10, candidate_tokens=100)


def test_sufficiency_accepts_good_answer():
    reqs = [Requirement("r1", "d1"), Requirement("r2", "d2")]
    ctx = _ctx_with_coverage(reqs, {"r1", "r2"})
    result = evaluate_sufficiency("The TTL is 900 seconds.", reqs, ctx)
    assert result.sufficient


def test_sufficiency_flags_admission():
    reqs = [Requirement("r1", "d1")]
    ctx = _ctx_with_coverage(reqs, {"r1"})
    result = evaluate_sufficiency(
        "The context does not contain information about this.", reqs, ctx
    )
    assert not result.sufficient
    assert "answer_admits_missing_context" in result.reasons


def test_sufficiency_flags_low_coverage():
    reqs = [Requirement(f"r{i}", f"d{i}") for i in range(1, 5)]
    ctx = _ctx_with_coverage(reqs, {"r1"})
    result = evaluate_sufficiency("Some plausible answer here.", reqs, ctx)
    assert not result.sufficient
    assert any(r.startswith("low_requirement_coverage") for r in result.reasons)


# ------------------------------------------------------------ requirements


def test_heuristic_requirements_from_symbols():
    profile = profile_task("Does AuthService.verify use the session_store module?")
    reqs = _heuristic_requirements(
        "Does AuthService.verify use the session_store module?", profile, 4
    )
    assert len(reqs) >= 2
    joined = " ".join(r.description for r in reqs)
    assert "AuthService" in joined or "session_store" in joined


# ------------------------------------------------------------ path routing


def test_fast_path_skips_requirement_model_call():
    """Factual questions must not pay the requirement-decomposition LLM call."""
    import asyncio

    from cortex.kernel.requirements import generate_requirements

    profile = profile_task("What is the payment gateway timeout?")
    assert profile.task_type == "factual"

    # allow_model=False must return heuristic requirements without touching
    # the model client at all (would raise: no runtime in unit tests).
    reqs, strategy = asyncio.get_event_loop().run_until_complete(
        generate_requirements("What is the payment gateway timeout?", profile,
                              allow_model=False)
    )
    assert strategy == "heuristic"
    assert len(reqs) >= 1


def test_deep_path_for_change_impact_questions():
    profile = profile_task("What breaks if SessionStore.get_session changes its return type?")
    assert profile.task_type == "multi_hop"  # deep path


def test_structural_questions_stay_deep():
    profile = profile_task("Which components import the auth service?")
    assert profile.task_type in ("structural", "multi_hop")


# -------------------------------------------------- inference budget controller


def test_budget_fast_path_skips_requirement_generation():
    from cortex.kernel.budget import InferenceBudgetController

    ctl = InferenceBudgetController(profile_task("What is the token TTL?"))
    assert ctl.fast_path and ctl.path == "fast"
    d = ctl.decide_requirement_generation()
    assert d.decision == "SKIP" and d.operation == "requirement_generation"
    assert ctl.decisions == [d]  # every decision is recorded exactly once


def test_budget_deep_path_executes_requirement_generation():
    from cortex.kernel.budget import InferenceBudgetController

    ctl = InferenceBudgetController(
        profile_task("What breaks if AuthService.verify changes?")
    )
    assert not ctl.fast_path and ctl.path == "deep"
    assert ctl.decide_requirement_generation().decision == "EXECUTE"


def test_budget_expansion_gate():
    from cortex.kernel.budget import InferenceBudgetController

    ctl = InferenceBudgetController(profile_task("What is X?"))
    # sufficient -> stop, no wasted round
    assert ctl.decide_expansion(
        sufficient=True, round_no=1, max_rounds=2, reasons=[]
    ).decision == "SKIP"
    # insufficient with rounds left -> spend another round
    esc = ctl.decide_expansion(
        sufficient=False, round_no=1, max_rounds=2, reasons=["low_coverage"]
    )
    assert esc.decision == "ESCALATE" and "low_coverage" in esc.reason
    # insufficient but out of rounds -> stop rather than loop forever
    assert ctl.decide_expansion(
        sufficient=False, round_no=2, max_rounds=2, reasons=["still_thin"]
    ).decision == "SKIP"
    assert len(ctl.decisions) == 3
