"""Engineering-intelligence endpoints (deterministic graph analyses).

Dead code, circular dependencies, repository insights, architecture layers and
request-flow tracing — all computed from the existing Knowledge Graph with no
inference cost. Read-only; safe to call any time on a ready version.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.db import get_session
from cortex.kernel.insights import (
    analyze_cycles,
    analyze_dead_code,
    analyze_flow,
    analyze_insights,
)

router = APIRouter(prefix="/v1/sources", tags=["insights"])


async def _require_ready(session: AsyncSession, version_id: uuid.UUID) -> None:
    row = (
        await session.execute(
            text("SELECT 1 FROM source_version WHERE id = :id AND status = 'ready'"),
            {"id": version_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="source version not found or not ready")


@router.get("/{version_id}/insights/dead-code")
async def dead_code(
    version_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    await _require_ready(session, version_id)
    return await analyze_dead_code(session, version_id)


@router.get("/{version_id}/insights/cycles")
async def cycles(
    version_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    await _require_ready(session, version_id)
    return await analyze_cycles(session, version_id)


@router.get("/{version_id}/insights/overview")
async def overview(
    version_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    await _require_ready(session, version_id)
    return await analyze_insights(session, version_id)


@router.get("/{version_id}/insights/flow")
async def flow(
    version_id: uuid.UUID,
    qualified_name: str = Query(..., description="entrypoint symbol or qualified_name"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _require_ready(session, version_id)
    return await analyze_flow(session, version_id, qualified_name)
