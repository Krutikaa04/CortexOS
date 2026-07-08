"""Execution endpoints: submit a query, inspect results, stream events."""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from cortex.db import get_session, get_session_factory

log = logging.getLogger("cortex.executions")

router = APIRouter(prefix="/v1/executions", tags=["executions"])

EVENT_POLL_SECONDS = 0.25
STREAM_TIMEOUT_SECONDS = 900


class CreateExecutionRequest(BaseModel):
    query: str
    mode: str = "cortex"  # 'cortex' | 'baseline'
    source_version_id: uuid.UUID | None = None  # default: latest ready version
    session_id: uuid.UUID | None = None  # links multi-turn SVM state


async def _resolve_version(session: AsyncSession, requested: uuid.UUID | None) -> uuid.UUID:
    if requested is not None:
        row = (
            await session.execute(
                text("SELECT id FROM source_version WHERE id = :id AND status = 'ready'"),
                {"id": requested},
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="source version not found or not ready")
        return row.id
    row = (
        await session.execute(
            text(
                "SELECT id FROM source_version WHERE status = 'ready' "
                "ORDER BY ingested_at DESC LIMIT 1"
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=409, detail="no ingested source available")
    return row.id


async def _run_pipeline(execution_id: uuid.UUID, mode: str, version_id: uuid.UUID,
                        query: str, session_id: uuid.UUID | None) -> None:
    """Background task: run the selected pipeline and persist the outcome."""
    factory = get_session_factory()
    try:
        if mode == "baseline":
            from cortex.baseline.pipeline import run_baseline_execution

            result = await run_baseline_execution(execution_id, version_id, query)
        else:
            from cortex.kernel.pipeline import run_cortex_execution

            result = await run_cortex_execution(execution_id, version_id, query, session_id)

        async with factory() as session:
            await session.execute(
                text(
                    "UPDATE execution SET status = 'succeeded', answer = :answer, "
                    "metrics = cast(:metrics as jsonb), finished_at = now() WHERE id = :id"
                ),
                {"id": execution_id, "answer": result["answer"],
                 "metrics": json.dumps(result["metrics"])},
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001 — outcome must always be recorded
        log.exception("execution %s failed", execution_id)
        from cortex.events import EventEmitter, EventType

        try:
            await EventEmitter(execution_id).emit(EventType.EXECUTION_FAILED, {"error": str(exc)})
        except Exception:  # noqa: BLE001
            pass
        async with factory() as session:
            await session.execute(
                text(
                    "UPDATE execution SET status = 'failed', failure_reason = :reason, "
                    "finished_at = now() WHERE id = :id"
                ),
                {"id": execution_id, "reason": str(exc)},
            )
            await session.commit()


@router.post("", status_code=202)
async def create_execution(
    body: CreateExecutionRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    if body.mode not in ("cortex", "baseline"):
        raise HTTPException(status_code=422, detail="mode must be 'cortex' or 'baseline'")
    version_id = await _resolve_version(session, body.source_version_id)

    execution_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO execution (id, source_version_id, session_id, mode, query, status) "
            "VALUES (:id, :vid, :sid, :mode, :query, 'running')"
        ),
        {"id": execution_id, "vid": version_id, "sid": body.session_id,
         "mode": body.mode, "query": body.query},
    )
    await session.commit()

    asyncio.create_task(
        _run_pipeline(execution_id, body.mode, version_id, body.query, body.session_id)
    )
    return {"execution_id": str(execution_id), "status": "running"}


@router.get("")
async def list_executions(
    limit: int = 50, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT id, mode, query, answer, status, failure_reason, metrics, "
                "source_version_id, session_id, started_at, finished_at "
                "FROM execution ORDER BY started_at DESC LIMIT :limit"
            ),
            {"limit": min(limit, 200)},
        )
    ).all()
    return [
        {
            "id": str(r.id),
            "mode": r.mode,
            "query": r.query,
            "answer": r.answer,
            "status": r.status,
            "failure_reason": r.failure_reason,
            "metrics": r.metrics,
            "source_version_id": str(r.source_version_id),
            "session_id": str(r.session_id) if r.session_id else None,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ]


@router.get("/{execution_id}")
async def get_execution(
    execution_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    row = (
        await session.execute(
            text(
                "SELECT id, mode, query, answer, status, failure_reason, metrics, "
                "source_version_id, session_id, started_at, finished_at "
                "FROM execution WHERE id = :id"
            ),
            {"id": execution_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="execution not found")
    return {
        "id": str(row.id),
        "mode": row.mode,
        "query": row.query,
        "answer": row.answer,
        "status": row.status,
        "failure_reason": row.failure_reason,
        "metrics": row.metrics,
        "source_version_id": str(row.source_version_id),
        "session_id": str(row.session_id) if row.session_id else None,
        "started_at": row.started_at.isoformat(),
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


@router.get("/{execution_id}/events")
async def list_events(
    execution_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT seq, event_type, payload, created_at FROM execution_event "
                "WHERE execution_id = :id ORDER BY seq"
            ),
            {"id": execution_id},
        )
    ).all()
    return [
        {"seq": r.seq, "event_type": r.event_type, "payload": r.payload,
         "ts": r.created_at.isoformat()}
        for r in rows
    ]


@router.get("/{execution_id}/stream")
async def stream_events(execution_id: uuid.UUID) -> StreamingResponse:
    """Server-Sent Events: live event stream until the execution finishes."""

    async def event_source():
        factory = get_session_factory()
        last_seq = 0
        elapsed = 0.0
        while elapsed < STREAM_TIMEOUT_SECONDS:
            async with factory() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT seq, event_type, payload, created_at "
                            "FROM execution_event "
                            "WHERE execution_id = :id AND seq > :last ORDER BY seq"
                        ),
                        {"id": execution_id, "last": last_seq},
                    )
                ).all()
                status = (
                    await session.execute(
                        text("SELECT status FROM execution WHERE id = :id"),
                        {"id": execution_id},
                    )
                ).scalar()

            for r in rows:
                last_seq = r.seq
                data = json.dumps(
                    {"seq": r.seq, "event_type": r.event_type, "payload": r.payload,
                     "ts": r.created_at.isoformat()},
                    default=str,
                )
                yield f"event: {r.event_type}\ndata: {data}\n\n"

            if status in ("succeeded", "failed"):
                yield f"event: DONE\ndata: {json.dumps({'status': status})}\n\n"
                return
            await asyncio.sleep(EVENT_POLL_SECONDS)
            elapsed += EVENT_POLL_SECONDS

    return StreamingResponse(event_source(), media_type="text/event-stream")
