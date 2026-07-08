"""Job queue over PostgreSQL.

Claiming uses FOR UPDATE SKIP LOCKED so multiple workers never double-run
a job. Crashed workers are recovered by lease expiry: a 'running' job whose
lock is older than its lease returns to the queue and is retried.

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

_WORKER_ID = f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"

_CLAIM_SQL = text(
    """
    WITH candidate AS (
        SELECT id FROM job
        WHERE status = 'queued'
           OR (status IN ('running', 'waiting_model')
               AND locked_at IS NOT NULL
               AND locked_at < now() - make_interval(secs => lease_seconds))
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


async def claim_next_job() -> dict[str, Any] | None:
    async with get_session_factory()() as session:
        row = (await session.execute(_CLAIM_SQL, {"worker_id": _WORKER_ID})).first()
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
    except Exception as exc:  # noqa: BLE001 — job failures must be recorded, not raised
        log.exception("job %s failed", job["id"])
        if job["attempts"] >= MAX_ATTEMPTS:
            await _finish(job["id"], "failed", error=str(exc))
        else:
            await _requeue(job["id"], error=str(exc))
        return
    await _finish(job["id"], "succeeded")


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
        await session.execute(
            text(
                "UPDATE job SET status = 'queued', error = :error, "
                "locked_by = NULL, locked_at = NULL WHERE id = :id"
            ),
            {"id": job_id, "error": error},
        )
        await session.commit()
    log.info("job %s requeued after error", job_id)


def _json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload)
