"""Change Impact Guard endpoint.

Accepts a unified diff for an ingested repository version and returns a
grounded impact report (blast radius, risk, tests, patch) computed by the
Kernel's impact analyzer. One synchronous model call; the rest is graph work.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.db import get_session
from cortex.kernel.impact import run_impact_analysis

router = APIRouter(prefix="/v1/sources", tags=["impact"])


class ImpactRequest(BaseModel):
    diff: str


@router.post("/{version_id}/impact")
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
    return await run_impact_analysis(session, version_id, body.diff)
