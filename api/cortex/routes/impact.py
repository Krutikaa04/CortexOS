"""Change Impact Guard endpoint.

Accepts a unified diff for an ingested repository version and analyzes its
blast radius with the Kernel. The analysis runs as a background execution
(mode='impact') so its phases stream over the shared execution event feed and
the long narrative model call never blocks the HTTP request. The finished
report is stored in the execution's ``metrics`` and read back by Studio.
"""

import asyncio
import json
import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.db import get_session, get_session_factory
from cortex.events import EventEmitter, EventType
from cortex.kernel.impact import run_impact_analysis

log = logging.getLogger("cortex.impact")

router = APIRouter(prefix="/v1/sources", tags=["impact"])


class ImpactRequest(BaseModel):
    diff: str


def _label(diff: str) -> str:
    paths = re.findall(r"\+\+\+ b/(\S+)", diff)
    if not paths:
        paths = re.findall(r"diff --git a/\S+ b/(\S+)", diff)
    if not paths:
        return "impact analysis"
    head = paths[0].split("/")[-1]
    extra = f" +{len(paths) - 1} more" if len(paths) > 1 else ""
    return f"impact: {head}{extra}"


async def _run_impact(execution_id: uuid.UUID, version_id: uuid.UUID, diff: str) -> None:
    """Background task: stream analysis phases, then persist the report."""
    factory = get_session_factory()
    emitter = EventEmitter(execution_id)
    try:
        async with factory() as session:
            report = await run_impact_analysis(session, version_id, diff, emitter=emitter)
        async with factory() as session:
            await session.execute(
                text(
                    "UPDATE execution SET status = 'succeeded', answer = :ans, "
                    "metrics = cast(:m as jsonb), finished_at = now() WHERE id = :id"
                ),
                {
                    "id": execution_id,
                    "ans": report.get("summary") or f"{report['risk_level']} risk",
                    "m": json.dumps(report, default=str),
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001 — outcome must always be recorded
        log.exception("impact execution %s failed", execution_id)
        try:
            await emitter.emit(EventType.EXECUTION_FAILED, {"error": str(exc)})
        except Exception:  # noqa: BLE001
            pass
        async with factory() as session:
            await session.execute(
                text(
                    "UPDATE execution SET status = 'failed', failure_reason = :r, "
                    "finished_at = now() WHERE id = :id"
                ),
                {"id": execution_id, "r": str(exc)},
            )
            await session.commit()


@router.post("/{version_id}/impact", status_code=202)
async def analyze_impact(
    version_id: uuid.UUID,
    body: ImpactRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    ready = (
        await session.execute(
            text("SELECT 1 FROM source_version WHERE id = :id AND status = 'ready'"),
            {"id": version_id},
        )
    ).first()
    if ready is None:
        raise HTTPException(status_code=404, detail="source version not found or not ready")
    if not body.diff.strip():
        raise HTTPException(status_code=422, detail="empty diff")

    execution_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO execution (id, source_version_id, mode, query, status) "
            "VALUES (:id, :vid, 'impact', :q, 'running')"
        ),
        {"id": execution_id, "vid": version_id, "q": _label(body.diff)},
    )
    await session.commit()

    asyncio.create_task(_run_impact(execution_id, version_id, body.diff))
    return {"execution_id": str(execution_id), "status": "running"}
