"""Benchmark endpoints: launch a suite, read the report."""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.db import get_session
from cortex.jobs import enqueue

router = APIRouter(prefix="/v1/benchmarks", tags=["benchmarks"])

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
    body: CreateBenchmarkRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    suite_path = SUITES_DIR / f"{body.suite}.json"
    if not suite_path.exists():
        raise HTTPException(status_code=404, detail=f"suite {body.suite!r} not found")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))

    if body.source_version_id:
        version_id = body.source_version_id
    else:
        row = (
            await session.execute(
                text("SELECT id FROM source_version WHERE status = 'ready' "
                     "ORDER BY ingested_at DESC LIMIT 1")
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
        {"benchmark_run_id": str(run_id), "questions": suite["questions"]},
    )
    return {"benchmark_run_id": str(run_id), "job_id": str(job_id), "status": "running"}


@router.get("")
async def list_benchmarks(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT id, name, status, created_at, finished_at, "
                "       report -> 'summary' AS summary "
                "FROM benchmark_run ORDER BY created_at DESC LIMIT 50"
            )
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
