"""Chat session endpoints.

A session is a named, repository-scoped conversation. Its *messages* are the
existing `execution` rows that carry the session_id (mode='cortex'), so this
module adds conversation management without a second memory system:

  list/create/rename/delete  -> chat_session metadata
  load a conversation        -> executions WHERE session_id = :id
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.db import get_session

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    source_version_id: uuid.UUID
    title: str | None = None


class RenameSessionRequest(BaseModel):
    title: str


@router.post("", status_code=201)
async def create_session(
    body: CreateSessionRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    ready = (
        await session.execute(
            text("SELECT 1 FROM source_version WHERE id = :id"),
            {"id": body.source_version_id},
        )
    ).first()
    if ready is None:
        raise HTTPException(status_code=404, detail="source version not found")
    sid = uuid.uuid4()
    title = (body.title or "New chat").strip()[:200] or "New chat"
    await session.execute(
        text(
            "INSERT INTO chat_session (id, source_version_id, title) "
            "VALUES (:id, :vid, :title)"
        ),
        {"id": sid, "vid": body.source_version_id, "title": title},
    )
    await session.commit()
    return {"id": str(sid), "source_version_id": str(body.source_version_id),
            "title": title, "message_count": 0, "last_activity": None}


@router.get("")
async def list_sessions(
    source_version_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    """Conversations for a repository, most-recently-active first.

    message_count and last_activity are derived from executions so session
    metadata never drifts from the actual messages."""
    rows = (
        await session.execute(
            text(
                "SELECT s.id, s.title, s.created_at, "
                "  count(e.id) FILTER (WHERE e.mode = 'cortex') AS msg_count, "
                "  max(e.started_at) AS last_activity "
                "FROM chat_session s "
                "LEFT JOIN execution e ON e.session_id = s.id "
                "WHERE s.source_version_id = :vid "
                "GROUP BY s.id, s.title, s.created_at "
                "ORDER BY coalesce(max(e.started_at), s.created_at) DESC"
            ),
            {"vid": source_version_id},
        )
    ).all()
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "message_count": int(r.msg_count or 0),
            "created_at": r.created_at.isoformat(),
            "last_activity": r.last_activity.isoformat() if r.last_activity else None,
        }
        for r in rows
    ]


@router.get("/{session_id}/messages")
async def session_messages(
    session_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    """Ordered transcript of a conversation, reconstructed from executions.

    Each message carries the answer, metrics, and the files that made it into
    the compiled context (from the CONTEXT_COMPILED event) so a reloaded
    conversation shows the same evidence a live one does."""
    rows = (
        await session.execute(
            text(
                "SELECT e.id, e.query, e.answer, e.status, e.failure_reason, e.metrics, "
                "  e.started_at, "
                "  (SELECT ev.payload FROM execution_event ev "
                "   WHERE ev.execution_id = e.id AND ev.event_type = 'CONTEXT_COMPILED' "
                "   ORDER BY ev.seq DESC LIMIT 1) AS compiled "
                "FROM execution e "
                "WHERE e.session_id = :sid AND e.mode = 'cortex' "
                "ORDER BY e.started_at"
            ),
            {"sid": session_id},
        )
    ).all()
    out: list[dict] = []
    for r in rows:
        included = (r.compiled or {}).get("included", []) if r.compiled else []
        files = [
            {"qualified_name": i["qualified_name"],
             "path": i["qualified_name"].split("::")[0],
             "symbol": i["qualified_name"].split("::")[-1],
             "representation": i.get("representation"), "tokens": i.get("tokens")}
            for i in included
        ]
        out.append({
            "id": str(r.id),
            "query": r.query,
            "answer": r.answer,
            "status": r.status,
            "failure_reason": r.failure_reason,
            "metrics": r.metrics,
            "files": files,
            "started_at": r.started_at.isoformat(),
        })
    return out


@router.patch("/{session_id}")
async def rename_session(
    session_id: uuid.UUID,
    body: RenameSessionRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    title = body.title.strip()[:200]
    if not title:
        raise HTTPException(status_code=422, detail="title cannot be empty")
    row = (
        await session.execute(
            text("UPDATE chat_session SET title = :t WHERE id = :id RETURNING id"),
            {"t": title, "id": session_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    await session.commit()
    return {"id": str(session_id), "title": title}


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    """Delete a conversation and its messages (events → executions → session)."""
    exec_ids = (
        await session.execute(
            text("SELECT id FROM execution WHERE session_id = :sid"),
            {"sid": session_id},
        )
    ).scalars().all()
    if exec_ids:
        await session.execute(
            text("DELETE FROM execution_event WHERE execution_id = ANY(:ids)"),
            {"ids": exec_ids},
        )
        await session.execute(
            text("DELETE FROM execution WHERE id = ANY(:ids)"), {"ids": exec_ids}
        )
    result = await session.execute(
        text("DELETE FROM chat_session WHERE id = :id"), {"id": session_id}
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="session not found")
