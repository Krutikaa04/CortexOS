"""CortexOS Kernel V1 execution pipeline.

Task Profiler -> Requirement Generator -> Hybrid Retrieval ->
Context Compiler -> LLM -> Sufficiency Evaluator (one expansion retry).

Every stage emits typed events; the metrics block mirrors the baseline
pipeline's schema plus compiler-specific numbers, so the benchmark
comparison is direct.
"""

import dataclasses
import logging
import time
import uuid
from typing import Any

from cortex.config import get_settings
from cortex.events import EventEmitter, EventType
from cortex.kernel.budget import InferenceBudgetController
from cortex.kernel.compiler import compile_context
from cortex.kernel.profiler import profile_task
from cortex.kernel.requirements import generate_requirements
from cortex.kernel.retriever import retrieve
from cortex.kernel.sufficiency import evaluate_sufficiency
from cortex.models_client import get_model_client
from cortex.tokens import estimate_tokens

log = logging.getLogger("cortex.kernel")

EXPANSION_BUDGET_FACTOR = 1.8
EXPANSION_TOP_K_BONUS = 6
MAX_ROUNDS = 2

PROMPT_TEMPLATE = """\
You are answering a question about a software repository. The context below
was compiled to contain only the information needed. Use only this context.
If the context does not contain the answer, say so.
{instruction}
CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""

# Intent-aware task instructions. "explain" is the empty default so the
# assembled prompt (and therefore the benchmark) is byte-identical to before;
# "debug" and "generate" ask the model for the structured output the product
# needs. Detection is deterministic keyword matching — no extra model call.
import re as _re

# Note: "breaks" is intentionally excluded — "what breaks if X changes" is a
# change-impact question, not a bug report, and must stay on the explain path.
_DEBUG_MARKERS = _re.compile(
    r"\b(fix|bug|broken|error|errors|fails?|failing|failed|crash(?:es|ing)?|"
    r"traceback|exception|regress(?:ion)?|incorrect|not working|doesn'?t work)\b",
    _re.IGNORECASE,
)
_GENERATE_MARKERS = _re.compile(
    r"\b(generate|write|implement|create|add|build|refactor|rewrite|scaffold)\b",
    _re.IGNORECASE,
)

_INSTRUCTIONS = {
    "explain": "",
    "debug": (
        "\nThe user is reporting a bug. Respond with these sections, each on its "
        "own line, using only the context:\n"
        "Diagnosis: what is going wrong.\n"
        "Root cause: the underlying reason, citing the responsible code.\n"
        "Evidence: the specific files/functions in the context that show it.\n"
        "Patch: a fenced code block with the corrected code.\n"
        "Explanation: why the patch fixes it.\n"
        "Affected files: the files that must change.\n"
    ),
    "generate": (
        "\nThe user is requesting code. Produce the actual code in a fenced code "
        "block first, grounded in the context's conventions, then a short "
        "explanation. Prefer complete, runnable code over description.\n"
    ),
}


def detect_intent(query: str) -> str:
    """Deterministically classify the query's intent: debug | generate | explain."""
    if _DEBUG_MARKERS.search(query):
        return "debug"
    if _GENERATE_MARKERS.search(query):
        return "generate"
    return "explain"

# Session mode: the context block is a stable, append-only prefix so the
# model runtime's KV cache reuses previously processed pages across turns.
SESSION_PROMPT_PREFIX = """\
You are answering questions about a software repository in an ongoing
session. Working-memory pages below stay resident across questions. Use
only this context. If it does not contain the answer, say so.

WORKING MEMORY:
"""


async def run_cortex_execution(
    execution_id: uuid.UUID,
    source_version_id: uuid.UUID,
    query: str,
    session_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    emitter = EventEmitter(execution_id)
    client = get_model_client()
    settings = get_settings()
    t_start = time.monotonic()

    await emitter.emit(EventType.TASK_RECEIVED, {"query": query, "mode": "cortex"})

    # --- 1. profile + deterministic path routing ---
    # The Inference Budget Controller owns every "should this expensive
    # operation happen?" decision. FAST: simple factual questions skip the
    # requirement-decomposition LLM call (measured 11-43s per question on
    # local CPU). DEEP: structural and multi-hop questions keep full
    # decomposition. The router is deterministic: no LLM call decides
    # whether to call an LLM, and every choice is recorded for the metrics.
    profile = profile_task(query)
    intent = detect_intent(query)
    instruction = _INSTRUCTIONS[intent]
    budget = InferenceBudgetController(profile)
    fast_path = budget.fast_path
    path = budget.path
    budget.decide_requirement_generation()
    await emitter.emit(
        EventType.TASK_PROFILED, {**profile.as_dict(), "path": path, "intent": intent}
    )

    generation_calls = 0
    embedding_calls = 0

    # --- 2. requirements ---
    t_requirements = time.monotonic()
    requirements, strategy = await generate_requirements(
        query, profile, allow_model=not fast_path
    )
    requirements_ms = int((time.monotonic() - t_requirements) * 1000)
    if strategy == "model":
        generation_calls += 1
    await emitter.emit(
        EventType.REQUIREMENTS_CREATED,
        {"strategy": strategy, "requirements": [r.as_dict() for r in requirements]},
    )

    # --- SVM: session mode keeps pages resident across turns ---
    resident_pages = []
    if session_id is not None:
        from cortex.svm import manager as svm_manager

        resident_pages = await svm_manager.get_active_pages(session_id)

    metrics: dict[str, Any] = {"rounds": 0}
    answer = ""
    context = None
    total_input_tokens = 0
    total_output_tokens = 0
    inference_ms = 0
    pages_reused = 0
    pages_faulted = 0

    for round_no in range(1, MAX_ROUNDS + 1):
        metrics["rounds"] = round_no

        # --- 3. retrieve ---
        await emitter.emit(
            EventType.RETRIEVAL_STARTED,
            {"strategy": "hybrid", "round": round_no,
             "top_k": profile.retrieval_top_k, "graph_depth": profile.dependency_depth},
        )
        t_retrieval = time.monotonic()
        candidates = await retrieve(source_version_id, requirements, profile)
        retrieval_ms = int((time.monotonic() - t_retrieval) * 1000)
        embedding_calls += 1  # retriever embeds all requirements in one batch
        for c in candidates[:30]:
            await emitter.emit(
                EventType.CANDIDATE_FOUND,
                {"qualified_name": c.qualified_name, "kind": c.kind,
                 "score": round(c.score, 4), "tokens": c.raw_token_count,
                 "requirements": sorted(c.requirements), "provenance": c.provenance[:5]},
            )

        # --- 4. compile (session mode: resident pages already serve their
        #     requirements at zero new-token cost; only non-resident
        #     candidates compete for the budget) ---
        resident_ids = {p.artifact_id for p in resident_pages}
        reused_candidates = [c for c in candidates if c.artifact_id in resident_ids]
        fresh_candidates = [c for c in candidates if c.artifact_id not in resident_ids]
        resident_covered: set[str] = set()
        for c in reused_candidates:
            resident_covered |= c.requirements

        t_compile = time.monotonic()
        context = compile_context(fresh_candidates, profile)
        compile_ms = int((time.monotonic() - t_compile) * 1000)
        for rejection in context.rejected:
            await emitter.emit(
                EventType.CANDIDATE_REJECTED,
                dataclasses.asdict(rejection),
            )
        await emitter.emit(
            EventType.CONTEXT_COMPILED,
            {
                "included": [
                    {"qualified_name": i.candidate.qualified_name,
                     "representation": i.representation, "tokens": i.token_count}
                    for i in context.included
                ],
                "compiled_tokens": context.total_tokens,
                "candidate_tokens": context.candidate_tokens,
                "reduction_pct": round(
                    100 * (1 - context.total_tokens / context.candidate_tokens), 1
                ) if context.candidate_tokens else 0.0,
                "budget": profile.context_budget_tokens,
            },
        )

        # --- 5. SVM paging + prompt assembly ---
        if session_id is not None:
            from cortex.svm import manager as svm_manager

            if reused_candidates:
                await svm_manager.touch_pages(
                    session_id, [c.artifact_id for c in reused_candidates]
                )
                pages_reused = len(reused_candidates)

            new_tokens = sum(i.token_count for i in context.included)
            for e in await svm_manager.evict_if_needed(session_id, new_tokens):
                await emitter.emit(EventType.EVICT, e)

            for item in context.included:
                await emitter.emit(
                    EventType.PAGE_FAULT,
                    {"qualified_name": item.candidate.qualified_name,
                     "requirements": sorted(item.candidate.requirements)},
                )
                seq = await svm_manager.page_in(
                    session_id, item.candidate.artifact_id,
                    item.representation, item.token_count,
                )
                await emitter.emit(
                    EventType.PAGE_IN,
                    {"qualified_name": item.candidate.qualified_name,
                     "representation": item.representation,
                     "tokens": item.token_count, "seq": seq},
                )
                pages_faulted += 1

            # Stable prefix: ALL resident pages in seq order (old first).
            resident_pages = await svm_manager.get_active_pages(session_id)
            memory_block = "\n\n".join(
                f"[page {p.seq}: {p.path} :: {p.qualified_name.split('::')[-1]}]\n{p.text}"
                for p in resident_pages
            )
            prompt = f"{SESSION_PROMPT_PREFIX}{memory_block}\n\nQUESTION: {query}\n\nANSWER:"
        else:
            prompt = PROMPT_TEMPLATE.format(
                context=context.render(), query=query, instruction=instruction
            )
        await emitter.emit(
            EventType.MODEL_SELECTED,
            {"model": settings.task_model, "reason": "single-model MVP"},
        )
        await emitter.emit(
            EventType.INFERENCE_STARTED,
            {"estimated_prompt_tokens": estimate_tokens(prompt), "round": round_no},
        )
        result = await client.generate(prompt)
        generation_calls += 1
        answer = result["text"].strip()
        total_input_tokens += result["input_tokens"]
        total_output_tokens += result["output_tokens"]
        inference_ms += result["duration_ms"]
        await emitter.emit(
            EventType.INFERENCE_COMPLETED,
            {"input_tokens": result["input_tokens"],
             "output_tokens": result["output_tokens"],
             "duration_ms": result["duration_ms"], "round": round_no},
        )

        # --- 6. sufficiency (resident pages count toward coverage) ---
        sufficiency = evaluate_sufficiency(
            answer, requirements, context, extra_covered=resident_covered
        )
        await emitter.emit(EventType.SUFFICIENCY_CHECKED, sufficiency.as_dict())
        expansion = budget.decide_expansion(
            sufficient=sufficiency.sufficient,
            round_no=round_no,
            max_rounds=MAX_ROUNDS,
            reasons=sufficiency.reasons,
        )
        if expansion.decision == "SKIP":
            break

        # --- expand and retry ---
        profile.context_budget_tokens = int(
            profile.context_budget_tokens * EXPANSION_BUDGET_FACTOR
        )
        profile.retrieval_top_k += EXPANSION_TOP_K_BONUS
        profile.dependency_depth = min(profile.dependency_depth + 1, 2)
        await emitter.emit(
            EventType.ESCALATION_TRIGGERED,
            {"reasons": sufficiency.reasons,
             "new_budget": profile.context_budget_tokens,
             "new_top_k": profile.retrieval_top_k},
        )

    metrics.update(
        {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "context_tokens_sent": context.total_tokens if context else 0,
            "candidate_tokens": context.candidate_tokens if context else 0,
            "context_reduction_pct": round(
                100 * (1 - context.total_tokens / context.candidate_tokens), 1
            ) if context and context.candidate_tokens else 0.0,
            "artifacts_included": len(context.included) if context else 0,
            "artifacts_rejected": len(context.rejected) if context else 0,
            "retrieval_ms": retrieval_ms,
            "inference_ms": inference_ms,
            "total_ms": int((time.monotonic() - t_start) * 1000),
            # inference-budget instrumentation: where the time and model
            # invocations actually went, and why each optional operation
            # ran or was skipped
            "path": path,
            "intent": intent,
            "requirements_ms": requirements_ms,
            "compile_ms": compile_ms,
            "generation_calls": generation_calls,
            "embedding_calls": embedding_calls,
            "decisions": [d.as_dict() for d in budget.decisions],
        }
    )
    if session_id is not None:
        metrics["svm"] = {
            "pages_reused": pages_reused,
            "pages_faulted_in": pages_faulted,
            "resident_pages": len(resident_pages),
            "resident_tokens": sum(p.tokens for p in resident_pages),
        }
    await emitter.emit(EventType.EXECUTION_COMPLETED, {"metrics": metrics})
    return {"answer": answer, "metrics": metrics}
