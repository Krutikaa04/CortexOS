"""Benchmark endpoints: launch a suite, read the report."""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.access import guard, user_of, version_owned
from cortex.db import get_session
from cortex.jobs import enqueue

router = APIRouter(prefix="/v1/benchmarks", tags=["benchmarks"], dependencies=[Depends(guard)])

SUITES_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "suites"


class CreateBenchmarkRequest(BaseModel):
    suite: str = "demo_store"  # file name in benchmark/suites (without .json)
    source_version_id: uuid.UUID | None = None


@router.get("/suites")
async def list_suites() -> list[dict]:
    suites = []
    for path in sorted(SUITES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        suites.append(
            {"suite": path.stem, "name": data.get("name"),
             "questions": len(data.get("questions", []))}
        )
    return suites


@router.post("", status_code=202)
async def create_benchmark(
    body: CreateBenchmarkRequest, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = user_of(request)
    suite_path = SUITES_DIR / f"{body.suite}.json"
    if not suite_path.exists():
        raise HTTPException(status_code=404, detail=f"suite {body.suite!r} not found")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))

    if body.source_version_id:
        version_id = body.source_version_id
        if not await version_owned(session, version_id, user):
            raise HTTPException(status_code=404, detail="source version not found")
    else:
        row = (
            await session.execute(
                text("SELECT v.id FROM source_version v JOIN source s ON s.id = v.source_id "
                     "WHERE v.status = 'ready' AND s.owner_id = :u "
                     "ORDER BY v.ingested_at DESC LIMIT 1"),
                {"u": user},
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=409, detail="no ingested source available")
        version_id = row.id

    run_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO benchmark_run (id, name, source_version_id, config, status) "
            "VALUES (:id, :name, :vid, cast(:config as jsonb), 'running')"
        ),
        {"id": run_id, "name": suite["name"], "vid": version_id,
         "config": json.dumps({"suite": body.suite})},
    )
    await session.commit()

    job_id = await enqueue(
        "run_benchmark",
        {"benchmark_run_id": str(run_id), "questions": suite["questions"], "owner_id": user},
    )
    return {"benchmark_run_id": str(run_id), "job_id": str(job_id), "status": "running"}


@router.get("")
async def list_benchmarks(
    request: Request, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT b.id, b.name, b.status, b.created_at, b.finished_at, "
                "       b.report -> 'summary' AS summary "
                "FROM benchmark_run b JOIN source_version v ON v.id = b.source_version_id "
                "JOIN source s ON s.id = v.source_id WHERE s.owner_id = :u "
                "ORDER BY b.created_at DESC LIMIT 50"
            ),
            {"u": user_of(request)}
        )
    ).all()
    return [
        {"id": str(r.id), "name": r.name, "status": r.status,
         "created_at": r.created_at.isoformat(),
         "finished_at": r.finished_at.isoformat() if r.finished_at else None,
         "summary": r.summary}
        for r in rows
    ]


@router.get("/{run_id}")
async def get_benchmark(run_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    row = (
        await session.execute(
            text("SELECT id, name, status, error, report, config, source_version_id, "
                 "created_at, finished_at FROM benchmark_run WHERE id = :id"),
            {"id": run_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="benchmark run not found")
    return {
        "id": str(row.id), "name": row.name, "status": row.status, "error": row.error,
        "config": row.config, "source_version_id": str(row.source_version_id),
        "report": row.report,
        "created_at": row.created_at.isoformat(),
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }
