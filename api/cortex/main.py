"""CortexOS control plane (FastAPI)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from cortex import __version__
from cortex.config import get_settings
from cortex.db import dispose_engine, get_session_factory
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

# A worker is considered live if its heartbeat is fresher than this.
WORKER_STALE_SECONDS = 30


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("cortex api starting: env=%s provider=%s version=%s",
             settings.env, settings.model_provider, __version__)
    yield
    # graceful shutdown: release DB connections so a rolling deploy doesn't
    # leak pooled connections against a managed Postgres connection cap
    await dispose_engine()
    log.info("cortex api stopped")


app = FastAPI(title="CortexOS Runtime", version=__version__, lifespan=lifespan)
app.include_router(sources_router)
app.include_router(graph_router)
app.include_router(impact_router)
app.include_router(executions_router)
app.include_router(benchmarks_router)
app.include_router(jobs_router)

_settings = get_settings()
# Production must name its allowed browser origins (the Vercel Studio URL);
# empty in production means same-origin only. In dev, reflect any origin.
if _settings.allowed_origins_list:
    _cors = {"allow_origins": _settings.allowed_origins_list}
elif not _settings.is_production:
    _cors = {"allow_origin_regex": ".*"}
else:
    _cors = {"allow_origins": []}
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    **_cors,
)


@app.get("/health/live")
async def liveness() -> JSONResponse:
    """Liveness: the process is up. No dependencies checked — a platform uses
    this to decide whether to restart the container, so it must not fail just
    because the database or model runtime is temporarily unavailable."""
    return JSONResponse(status_code=200, content={"status": "alive", "version": __version__})


@app.get("/health")
async def health() -> JSONResponse:
    """Readiness + detailed status of every runtime dependency.

    200 "ok" when the database and all required models are ready; 200
    "degraded" while models are still pulling or no worker is live (so a
    platform's startup probe is not deadlocked on a multi-GB model pull); 503
    "unavailable" when the database is unreachable (nothing can be served).
    """
    settings = get_settings()
    checks: dict[str, str] = {"api": "ok"}

    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
            worker_row = (
                await session.execute(
                    text(
                        "SELECT kinds, extract(epoch from (now() - last_seen)) AS age "
                        "FROM worker_heartbeat ORDER BY last_seen DESC LIMIT 1"
                    )
                )
            ).first()
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — health must never crash
        log.error("health: database unreachable: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "version": __version__,
                     "checks": {"api": "ok", "database": "unreachable"}},
        )

    # worker + repository indexer (the indexer runs on the ingestion worker)
    if worker_row is None:
        checks["worker"] = "none"
        checks["repository_indexer"] = "unavailable"
    elif worker_row.age is not None and worker_row.age <= WORKER_STALE_SECONDS:
        checks["worker"] = "alive"
        checks["repository_indexer"] = "ready"
    else:
        checks["worker"] = f"stale ({int(worker_row.age)}s)"
        checks["repository_indexer"] = "unavailable"

    # model provider
    provider = get_model_client()
    checks["model_provider"] = provider.name
    try:
        missing = await provider.missing_models()
        checks["models"] = "ok" if not missing else f"pulling: {', '.join(missing)}"
    except ModelUnavailableError:
        checks["models"] = "unreachable"

    ready = checks["database"] == "ok" and checks["models"] == "ok"
    degraded = not ready or checks["worker"] != "alive"
    return JSONResponse(
        status_code=200,
        content={
            "status": "degraded" if degraded else "ok",
            "version": __version__,
            "ready": ready,
            "checks": checks,
        },
    )
