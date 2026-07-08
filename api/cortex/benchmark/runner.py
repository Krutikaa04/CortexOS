"""Benchmark harness: baseline vs CortexOS, paired on identical questions.

Fairness invariants:
- same source_version (identical snapshot),
- same task + embedding models,
- same question order,
- token counts come from the model runtime, never estimated.

Quality scoring (MVP): each question declares expected_keywords; an answer
scores the fraction of keyword groups it contains (a group like
["900", "15 min"] is satisfied by ANY of its variants). This is a cheap,
transparent metric — a judge model can be layered on later, but keyword
truth never lies about what the answer literally contains.
"""

import logging
import statistics
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from cortex.baseline.pipeline import run_baseline_execution
from cortex.config import get_settings
from cortex.db import get_session_factory
from cortex.jobs import HANDLERS
from cortex.kernel.pipeline import run_cortex_execution

log = logging.getLogger("cortex.benchmark")

MODES = ("baseline", "cortex")


async def handle_run_benchmark(job_id: uuid.UUID, payload: dict[str, Any]) -> None:
    """Job handler.

    payload = {
      "benchmark_run_id": uuid,          # pre-created by the API
      "questions": [{"id", "question", "category", "expected_keywords": [[...], ...]}],
    }
    """
    run_id = uuid.UUID(payload["benchmark_run_id"])
    questions = payload["questions"]
    factory = get_session_factory()

    async with factory() as session:
        version_id = (
            await session.execute(
                text("SELECT source_version_id FROM benchmark_run WHERE id = :id"),
                {"id": run_id},
            )
        ).scalar_one()

    results: list[dict] = []
    try:
        for q in questions:
            row: dict[str, Any] = {"id": q["id"], "category": q.get("category", "unknown")}
            for mode in MODES:
                execution_id = await _create_execution(run_id, version_id, mode, q["question"])
                try:
                    if mode == "baseline":
                        out = await run_baseline_execution(execution_id, version_id, q["question"])
                    else:
                        out = await run_cortex_execution(execution_id, version_id, q["question"])
                    quality = _keyword_score(out["answer"], q.get("expected_keywords", []))
                    await _finish_execution(execution_id, "succeeded", out)
                    row[mode] = {
                        "execution_id": str(execution_id),
                        "answer": out["answer"],
                        "quality": quality,
                        **{k: out["metrics"].get(k) for k in
                           ("input_tokens", "output_tokens", "total_ms", "rounds")},
                    }
                except Exception as exc:  # noqa: BLE001 — record, keep benchmarking
                    log.exception("benchmark execution failed (%s, %s)", q["id"], mode)
                    await _finish_execution(execution_id, "failed", error=str(exc))
                    row[mode] = {"execution_id": str(execution_id), "error": str(exc),
                                 "quality": 0.0}
            results.append(row)
            log.info("benchmark %s: question %s done", run_id, q["id"])

        report = _build_report(results)
        async with factory() as session:
            await session.execute(
                text(
                    "UPDATE benchmark_run SET status = 'succeeded', "
                    "report = cast(:report as jsonb), finished_at = now() WHERE id = :id"
                ),
                {"id": run_id, "report": _json(report)},
            )
            await session.commit()
    except Exception as exc:
        async with factory() as session:
            await session.execute(
                text(
                    "UPDATE benchmark_run SET status = 'failed', error = :err, "
                    "finished_at = now() WHERE id = :id"
                ),
                {"id": run_id, "err": str(exc)},
            )
            await session.commit()
        raise


HANDLERS["run_benchmark"] = handle_run_benchmark


def _keyword_score(answer: str, keyword_groups: list[list[str]]) -> float:
    """Fraction of groups satisfied; a group passes if ANY variant appears."""
    if not keyword_groups:
        return 0.0
    answer_lower = answer.lower()
    hit = sum(
        1 for group in keyword_groups
        if any(variant.lower() in answer_lower for variant in group)
    )
    return hit / len(keyword_groups)


def _build_report(results: list[dict]) -> dict:
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": {
            "task_model": get_settings().task_model,
            "embed_model": get_settings().embed_model,
        },
        "question_count": len(results),
        "per_question": results,
    }
    summary: dict[str, Any] = {}
    for mode in MODES:
        ok = [r[mode] for r in results if "error" not in r.get(mode, {"error": 1})]
        if not ok:
            summary[mode] = {"completed": 0}
            continue
        summary[mode] = {
            "completed": len(ok),
            "failed": len(results) - len(ok),
            "mean_input_tokens": round(statistics.mean(r["input_tokens"] for r in ok), 1),
            "median_input_tokens": statistics.median(r["input_tokens"] for r in ok),
            "mean_quality": round(statistics.mean(r["quality"] for r in ok), 3),
            "mean_total_ms": round(statistics.mean(r["total_ms"] for r in ok), 0),
        }
    if summary.get("baseline", {}).get("completed") and summary.get("cortex", {}).get("completed"):
        b, c = summary["baseline"], summary["cortex"]
        summary["comparison"] = {
            "input_token_reduction_pct": round(
                100 * (1 - c["mean_input_tokens"] / b["mean_input_tokens"]), 1
            ),
            "quality_retention_pct": round(
                100 * (c["mean_quality"] / b["mean_quality"]), 1
            ) if b["mean_quality"] else None,
            "latency_ratio": round(c["mean_total_ms"] / b["mean_total_ms"], 2)
            if b["mean_total_ms"] else None,
        }
    report["summary"] = summary
    return report


async def _create_execution(
    run_id: uuid.UUID, version_id: uuid.UUID, mode: str, query: str
) -> uuid.UUID:
    execution_id = uuid.uuid4()
    async with get_session_factory()() as session:
        await session.execute(
            text(
                "INSERT INTO execution "
                "(id, source_version_id, mode, query, status, benchmark_run_id) "
                "VALUES (:id, :vid, :mode, :q, 'running', :rid)"
            ),
            {"id": execution_id, "vid": version_id, "mode": mode, "q": query, "rid": run_id},
        )
        await session.commit()
    return execution_id


async def _finish_execution(
    execution_id: uuid.UUID, status: str,
    out: dict | None = None, error: str | None = None,
) -> None:
    async with get_session_factory()() as session:
        await session.execute(
            text(
                "UPDATE execution SET status = :status, answer = :answer, "
                "metrics = cast(:metrics as jsonb), failure_reason = :err, "
                "finished_at = now() WHERE id = :id"
            ),
            {
                "id": execution_id, "status": status,
                "answer": (out or {}).get("answer"),
                "metrics": _json((out or {}).get("metrics", {})),
                "err": error,
            },
        )
        await session.commit()


def _json(value: Any) -> str:
    import json

    return json.dumps(value, default=str)
