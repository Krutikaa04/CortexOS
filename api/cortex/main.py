"""CortexOS control plane (FastAPI)."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from cortex import __version__
from cortex.config import get_settings
from cortex.db import get_session_factory
from cortex.models_client import ModelUnavailableError, get_model_client
from cortex.routes.benchmarks import router as benchmarks_router
from cortex.routes.executions import router as executions_router
from cortex.routes.graph import router as graph_router
from cortex.routes.impact import router as impact_router
from cortex.routes.jobs import router as jobs_router
from cortex.routes.sources import router as sources_router

logging.basicConfig(
    level=get_settings().log_level,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
log = logging.getLogger("cortex.api")

app = FastAPI(title="CortexOS Runtime", version=__version__)
app.include_router(sources_router)
app.include_router(graph_router)
app.include_router(impact_router)
app.include_router(executions_router)
app.include_router(benchmarks_router)
app.include_router(jobs_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if get_settings().env == "dev" else [],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> JSONResponse:
    """Liveness + readiness.

    Returns 200 with status "ok" when DB and all required models are ready,
    200 with status "degraded" while models are still pulling (so Compose
    startup is not deadlocked on a multi-GB download), and 503 when the
    database is unreachable.
    """
    checks: dict[str, str] = {}

    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — health must never crash
        log.error("health: database unreachable: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "checks": {"database": "unreachable"}},
        )

    try:
        missing = await get_model_client().missing_models()
        checks["models"] = "ok" if not missing else f"pulling: {', '.join(missing)}"
    except ModelUnavailableError:
        checks["models"] = "unreachable"

    degraded = checks["models"] != "ok"
    return JSONResponse(
        status_code=200,
        content={
            "status": "degraded" if degraded else "ok",
            "version": __version__,
            "checks": checks,
        },
    )
