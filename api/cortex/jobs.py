"""Job queue over PostgreSQL.

Claiming uses FOR UPDATE SKIP LOCKED so multiple workers never double-run
a job, and is **kind-filtered**: a worker claims only the job kinds in its
lane, so a long-running benchmark can never block repository ingestion.
Crashed workers are recovered by lease expiry.

Cancellation is cooperative:
  queued                 -> cancel -> cancelled            (immediate)
  running/waiting_model  -> cancel -> cancellation_requested
                            worker hits a checkpoint       -> cancelled
  cancellation_requested -> cancel -> no-op (idempotent)
  terminal               -> cancel -> typed conflict for the API layer

Workers call `checkpoint(job_id)` between safe units of work; it raises
JobCancelled when cancellation was requested, and doubles as the progress
reporter (stage + done/total). Cancelled jobs are never retried.

Handlers register themselves in HANDLERS as pipelines land
(ingestion, benchmarks).
"""

import logging
import socket
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import text

from cortex.db import get_session_factory

log = logging.getLogger("cortex.jobs")

# kind -> async handler(job_id, payload) — populated as pipelines are implemented
HANDLERS: dict[str, Callable[[uuid.UUID, dict[str, Any]], Awaitable[None]]] = {}

MAX_ATTEMPTS = 3

TERMINAL_STATUSES = ("succeeded", "failed", "cancelled")

_WORKER_ID = f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"


class JobCancelled(Exception):
    """Raised inside a handler when cancellation was requested."""


_CLAIM_SQL = text(
    """
    WITH candidate AS (
        SELECT id FROM job
        WHERE kind = ANY(:kinds)
          AND (status = 'queued'
               OR (status IN ('running', 'waiting_model')
                   AND locked_at IS NOT NULL
                   AND locked_at < now() - make_interval(secs => lease_seconds)))
        ORDER BY created_at
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    UPDATE job SET
        status = 'running',
        locked_by = :worker_id,
        locked_at = now(),
        attempts = attempts + 1
    FROM candidate
    WHERE job.id = candidate.id
    RETURNING job.id, job.kind, job.payload, job.attempts
    """
)

# A cancellation_requested job whose worker died mid-flight must not stay
# stuck: once its lease expires there is no worker left to acknowledge, so
# it is finalized as cancelled directly.
_SWEEP_ORPHANED_CANCELS_SQL = text(
    """
    UPDATE job SET status = 'cancelled', finished_at = now(), locked_by = NULL
    WHERE status = 'cancellation_requested'
      AND locked_at IS NOT NULL
      AND locked_at < now() - make_interval(secs => lease_seconds)
    """
)


async def enqueue(kind: str, payload: dict[str, Any]) -> uuid.UUID:
    async with get_session_factory()() as session:
        result = await session.execute(
            text(
                "INSERT INTO job (id, kind, payload, status) "
                "VALUES (:id, :kind, cast(:payload as jsonb), 'queued') RETURNING id"
            ),
            {"id": uuid.uuid4(), "kind": kind, "payload": _json(payload)},
        )
        await session.commit()
        job_id = result.scalar_one()
        log.info("enqueued job %s kind=%s", job_id, kind)
        return job_id


async def claim_next_job(kinds: list[str] | None = None) -> dict[str, Any] | None:
    """Claim the oldest queued job of the given kinds (all kinds if None)."""
    if kinds is None:
        kinds = list(HANDLERS.keys())
    if not kinds:
        return None
    async with get_session_factory()() as session:
        await session.execute(_SWEEP_ORPHANED_CANCELS_SQL)
        row = (
            await session.execute(_CLAIM_SQL, {"worker_id": _WORKER_ID, "kinds": kinds})
        ).first()
        await session.commit()
    if row is None:
        return None
    job = {"id": row.id, "kind": row.kind, "payload": row.payload, "attempts": row.attempts}
    log.info("claimed job %s kind=%s attempt=%d", job["id"], job["kind"], job["attempts"])
    return job


async def run_job(job: dict[str, Any]) -> None:
    handler = HANDLERS.get(job["kind"])
    if handler is None:
        await _finish(job["id"], "failed", error=f"no handler for kind {job['kind']!r}")
        return
    try:
        await handler(job["id"], job["payload"])
    except JobCancelled:
        await _finish(job["id"], "cancelled")
        return
    except Exception as exc:  # noqa: BLE001 — job failures must be recorded, not raised
        log.exception("job %s failed", job["id"])
        if job["attempts"] >= MAX_ATTEMPTS:
            await _finish(job["id"], "failed", error=str(exc))
        else:
            await _requeue(job["id"], error=str(exc))
        return
    await _finish(job["id"], "succeeded")


async def checkpoint(
    job_id: uuid.UUID,
    stage: str | None = None,
    done: int | None = None,
    total: int | None = None,
) -> None:
    """Progress + cancellation checkpoint, called at safe work boundaries.

    Updates the job's reported stage/progress (when given), refreshes the
    lease heartbeat, and raises JobCancelled if cancellation was requested.
    `total` may be honestly unknown (None) — the API exposes exactly that.
    """
    progress = None
    if done is not None:
        progress = _json({"done": done, "total": total})
    async with get_session_factory()() as session:
        row = (
            await session.execute(
                text(
                    "UPDATE job SET "
                    "  locked_at = now(), "
                    "  stage = coalesce(:stage, stage), "
                    "  progress = coalesce(cast(:progress as jsonb), progress) "
                    "WHERE id = :id RETURNING status"
                ),
                {"id": job_id, "stage": stage, "progress": progress},
            )
        ).first()
        await session.commit()
    if row is not None and row.status == "cancellation_requested":
        log.info("job %s acknowledging cancellation at stage %s", job_id, stage)
        raise JobCancelled(str(job_id))


async def request_cancel(job_id: uuid.UUID) -> str | None:
    """Cancel a job. Returns the resulting status, or None if not found.

    queued -> 'cancelled'; running/waiting_model -> 'cancellation_requested';
    cancellation_requested -> unchanged (idempotent); terminal -> the
    terminal status unchanged (the API layer turns that into a conflict).
    """
    async with get_session_factory()() as session:
        row = (
            await session.execute(
                text(
                    "UPDATE job SET "
                    "  status = CASE "
                    "    WHEN status = 'queued' THEN 'cancelled' "
                    "    WHEN status IN ('running', 'waiting_model') "
                    "         THEN 'cancellation_requested' "
                    "    ELSE status END, "
                    "  finished_at = CASE WHEN status = 'queued' THEN now() "
                    "                     ELSE finished_at END "
                    "WHERE id = :id RETURNING status"
                ),
                {"id": job_id},
            )
        ).first()
        await session.commit()
    return row.status if row else None


async def _finish(job_id: uuid.UUID, status: str, *, error: str | None = None) -> None:
    async with get_session_factory()() as session:
        await session.execute(
            text(
                "UPDATE job SET status = :status, error = :error, "
                "finished_at = now(), locked_by = NULL WHERE id = :id"
            ),
            {"id": job_id, "status": status, "error": error},
        )
        await session.commit()
    log.info("job %s -> %s", job_id, status)


async def _requeue(job_id: uuid.UUID, *, error: str) -> None:
    async with get_session_factory()() as session:
        # A cancellation that arrived while the job was failing wins:
        # intentionally cancelled work is never retried.
        await session.execute(
            text(
                "UPDATE job SET "
                "  status = CASE WHEN status = 'cancellation_requested' "
                "                THEN 'cancelled' ELSE 'queued' END, "
                "  finished_at = CASE WHEN status = 'cancellation_requested' "
                "                     THEN now() ELSE finished_at END, "
                "  error = :error, locked_by = NULL, locked_at = NULL "
                "WHERE id = :id"
            ),
            {"id": job_id, "error": error},
        )
        await session.commit()
    log.info("job %s requeued after error", job_id)


def _json(payload: Any) -> str:
    import json

    return json.dumps(payload)
