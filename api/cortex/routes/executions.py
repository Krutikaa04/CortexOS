"""Execution endpoints: submit a query, inspect results, stream events."""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from cortex.access import guard, user_of
from cortex.db import get_session, get_session_factory

log = logging.getLogger("cortex.executions")

router = APIRouter(prefix="/v1/executions", tags=["executions"], dependencies=[Depends(guard)])

EVENT_POLL_SECONDS = 0.25
STREAM_TIMEOUT_SECONDS = 900


class CreateExecutionRequest(BaseModel):
    query: str
    mode: str = "cortex"  # 'cortex' | 'baseline'
    source_version_id: uuid.UUID | None = None  # default: latest ready version
    session_id: uuid.UUID | None = None  # links multi-turn SVM state
    no_cache: bool = False  # force a fresh run instead of re-serving a cached answer


async def _resolve_version(
    session: AsyncSession, requested: uuid.UUID | None, user: str
) -> uuid.UUID:
    if requested is not None:
        row = (
            await session.execute(
                text("SELECT v.id FROM source_version v JOIN source s ON s.id = v.source_id "
                     "WHERE v.id = :id AND v.status = 'ready' AND s.owner_id = :u"),
                {"id": requested, "u": user},
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="source version not found or not ready")
        return row.id
    row = (
        await session.execute(
            text(
                "SELECT v.id FROM source_version v JOIN source s ON s.id = v.source_id "
                "WHERE v.status = 'ready' AND s.owner_id = :u "
                "ORDER BY v.ingested_at DESC LIMIT 1"
            ),
            {"u": user},
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=409, detail="no ingested source available")
    return row.id


async def _run_pipeline(execution_id: uuid.UUID, mode: str, version_id: uuid.UUID,
                        query: str, session_id: uuid.UUID | None,
                        cache_key: str | None = None) -> None:
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
            if cache_key:
                from cortex import answer_cache

                await answer_cache.store(session, cache_key, version_id, query,
                                         execution_id, result["answer"], result["metrics"])
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
    body: CreateExecutionRequest, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    if body.mode not in ("cortex", "baseline"):
        raise HTTPException(status_code=422, detail="mode must be 'cortex' or 'baseline'")
    version_id = await _resolve_version(session, body.source_version_id, user_of(request))
    if body.session_id is not None:
        # a chat session is bound to one repository; never mix repositories
        owner = (await session.execute(
            text("SELECT source_version_id FROM chat_session WHERE id = :id"),
            {"id": body.session_id})).first()
        if owner is not None and owner.source_version_id != version_id:
            raise HTTPException(status_code=409, detail="session belongs to a different repository")

    execution_id = uuid.uuid4()
    cache_key = None
    if body.mode == "cortex":
        from cortex import answer_cache

        graph_stats = (await session.execute(
            text("SELECT stats->'graph' FROM source_version WHERE id = :id"),
            {"id": version_id})).scalar_one_or_none()
        cache_key = answer_cache.make_key(version_id, body.query, graph_stats)
        hit = None if body.no_cache else await answer_cache.lookup(session, cache_key)
        if hit is not None:
            # Re-serve the stored answer, metrics and event trail as a new,
            # already-finished execution (so history and the UI work unchanged).
            metrics = {**hit["metrics"], "cache": {
                "hit": True, "source_execution_id": str(hit["execution_id"])}}
            await session.execute(
                text(
                    "INSERT INTO execution (id, source_version_id, session_id, mode, query, "
                    "answer, status, metrics, finished_at) VALUES (:id, :vid, :sid, 'cortex', "
                    ":query, :answer, 'succeeded', cast(:metrics as jsonb), now())"
                ),
                {"id": execution_id, "vid": version_id, "sid": body.session_id,
                 "query": body.query, "answer": hit["answer"], "metrics": json.dumps(metrics)},
            )
            await session.execute(
                text(
                    "INSERT INTO execution_event (execution_id, seq, event_type, payload) "
                    "SELECT :new, seq, event_type, payload FROM execution_event "
                    "WHERE execution_id = :src"
                ),
                {"new": execution_id, "src": hit["execution_id"]},
            )
            await session.commit()
            return {"execution_id": str(execution_id), "status": "succeeded", "cached": True}

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
        _run_pipeline(execution_id, body.mode, version_id, body.query, body.session_id,
                      cache_key)
    )
    return {"execution_id": str(execution_id), "status": "running"}


@router.get("")
async def list_executions(
    request: Request, limit: int = 50, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT e.id, e.mode, e.query, e.answer, e.status, e.failure_reason, "
                "e.metrics, e.source_version_id, e.session_id, e.started_at, e.finished_at "
                "FROM execution e JOIN source_version v ON v.id = e.source_version_id "
                "JOIN source s ON s.id = v.source_id WHERE s.owner_id = :u "
                "ORDER BY e.started_at DESC LIMIT :limit"
            ),
            {"limit": min(limit, 200), "u": user_of(request)},
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


@router.post("/{execution_id}/stream-ticket")
async def stream_ticket(execution_id: uuid.UUID, request: Request) -> dict:
    """Issue a short-lived ticket for the SSE stream (ownership is enforced by
    the router guard on {execution_id})."""
    from cortex.security import make_stream_ticket

    return {"ticket": make_stream_ticket(str(execution_id), user_of(request))}


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
