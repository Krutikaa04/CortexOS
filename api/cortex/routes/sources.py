"""Source ingestion endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.db import get_session
from cortex.jobs import enqueue

router = APIRouter(prefix="/v1/sources", tags=["sources"])


class CreateSourceRequest(BaseModel):
    uri: str
    ref: str | None = None
    display_name: str | None = None


@router.post("", status_code=202)
async def create_source(body: CreateSourceRequest) -> dict:
    """Queue ingestion of a Git repository (remote URL or local path)."""
    job_id = await enqueue(
        "ingest_source",
        {"uri": body.uri, "ref": body.ref, "display_name": body.display_name},
    )
    return {"job_id": str(job_id), "status": "queued"}


@router.get("")
async def list_sources(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT s.id, s.uri, s.display_name, v.id AS version_id, "
                "       v.commit_sha, v.status, v.stats, v.ingested_at "
                "FROM source s "
                "LEFT JOIN LATERAL ("
                "  SELECT * FROM source_version "
                "  WHERE source_id = s.id ORDER BY ingested_at DESC LIMIT 1"
                ") v ON true "
                "ORDER BY s.created_at"
            )
        )
    ).all()
    return [
        {
            "id": str(r.id),
            "uri": r.uri,
            "display_name": r.display_name,
            "latest_version": {
                "id": str(r.version_id),
                "commit_sha": r.commit_sha,
                "status": r.status,
                "stats": r.stats,
                "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
            }
            if r.version_id
            else None,
        }
        for r in rows
    ]


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    """Compatibility alias for GET /v1/jobs/{job_id}."""
    from cortex.routes.jobs import get_job as get_job_v1

    return await get_job_v1(job_id, session)
