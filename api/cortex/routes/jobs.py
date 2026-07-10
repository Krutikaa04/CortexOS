"""Job inspection and cancellation endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.db import get_session
from cortex.jobs import TERMINAL_STATUSES, request_cancel

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])

_JOB_SQL = text(
    "SELECT id, kind, status, stage, progress, attempts, error, "
    "created_at, locked_at, finished_at, payload FROM job WHERE id = :id"
)


def _serialize(row) -> dict:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "status": row.status,
        # stage/progress are worker-reported facts; null means honestly unknown
        "stage": row.stage,
        "progress": row.progress,
        "attempts": row.attempts,
        "error": row.error,
        "created_at": row.created_at.isoformat(),
        "started_at": row.locked_at.isoformat() if row.locked_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        # safe, useful payload context without leaking internals
        "uri": (row.payload or {}).get("uri"),
    }


@router.get("/{job_id}")
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    row = (await session.execute(_JOB_SQL, {"id": job_id})).first()
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _serialize(row)


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    status = await request_cancel(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="job not found")
    if status in TERMINAL_STATUSES and status != "cancelled":
        raise HTTPException(
            status_code=409, detail=f"job already finished with status {status!r}"
        )
    row = (await session.execute(_JOB_SQL, {"id": job_id})).first()
    return _serialize(row)
