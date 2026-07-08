"""Baseline RAG pipeline — the conventional system CortexOS must beat.

Query -> embed -> top-K chunk retrieval -> prompt construction -> LLM -> answer.

Deliberately conventional: fixed K, fixed chunks, no profiling, no
compilation, no memory. Its metrics are logged with the same schema as
CortexOS executions so benchmark comparisons are direct and fair.
"""

import logging
import time
import uuid
from typing import Any

from sqlalchemy import text

from cortex.config import get_settings
from cortex.db import get_session_factory
from cortex.events import EventEmitter, EventType
from cortex.models_client import get_model_client
from cortex.tokens import estimate_tokens

log = logging.getLogger("cortex.baseline")

TOP_K = 10

PROMPT_TEMPLATE = """\
You are answering a question about a software repository. Use only the
provided context. If the context does not contain the answer, say so.

CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""


async def run_baseline_execution(
    execution_id: uuid.UUID,
    source_version_id: uuid.UUID,
    query: str,
) -> dict[str, Any]:
    """Execute one baseline query. Returns {"answer", "metrics"}."""
    emitter = EventEmitter(execution_id)
    client = get_model_client()
    settings = get_settings()
    t_start = time.monotonic()

    await emitter.emit(EventType.TASK_RECEIVED, {"query": query, "mode": "baseline"})

    # Retrieve top-K chunks by cosine similarity
    await emitter.emit(EventType.RETRIEVAL_STARTED, {"strategy": "fixed_top_k", "k": TOP_K})
    t_retrieval = time.monotonic()
    query_embedding = (await client.embed([query]))[0]
    async with get_session_factory()() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT bc.id, bc.text, bc.token_count, sf.path, "
                    "       1 - (bc.embedding <=> cast(:qe as vector)) AS similarity "
                    "FROM baseline_chunk bc "
                    "JOIN source_file sf ON sf.id = bc.source_file_id "
                    "WHERE bc.source_version_id = :vid "
                    "ORDER BY bc.embedding <=> cast(:qe as vector) "
                    "LIMIT :k"
                ),
                {"qe": str(query_embedding), "vid": source_version_id, "k": TOP_K},
            )
        ).all()
    retrieval_ms = int((time.monotonic() - t_retrieval) * 1000)

    for r in rows:
        await emitter.emit(
            EventType.CANDIDATE_FOUND,
            {"chunk_id": str(r.id), "path": r.path, "similarity": round(r.similarity, 4),
             "tokens": r.token_count},
        )

    context = "\n\n---\n\n".join(f"[{r.path}]\n{r.text}" for r in rows)
    prompt = PROMPT_TEMPLATE.format(context=context, query=query)

    await emitter.emit(
        EventType.MODEL_SELECTED,
        {"model": settings.task_model, "reason": "fixed baseline model"},
    )
    await emitter.emit(
        EventType.INFERENCE_STARTED,
        {"estimated_prompt_tokens": estimate_tokens(prompt)},
    )
    result = await client.generate(prompt)
    await emitter.emit(
        EventType.INFERENCE_COMPLETED,
        {"input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
         "duration_ms": result["duration_ms"]},
    )

    total_ms = int((time.monotonic() - t_start) * 1000)
    metrics = {
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "context_tokens_sent": sum(r.token_count for r in rows),
        "retrieved_chunks": len(rows),
        "retrieval_ms": retrieval_ms,
        "inference_ms": result["duration_ms"],
        "total_ms": total_ms,
    }
    await emitter.emit(EventType.EXECUTION_COMPLETED, {"metrics": metrics})
    return {"answer": result["text"].strip(), "metrics": metrics}
