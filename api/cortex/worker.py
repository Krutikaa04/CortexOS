"""CortexOS background worker.

Polls the PostgreSQL-backed job queue (SELECT ... FOR UPDATE SKIP LOCKED)
and executes long-running work: repository ingestion, benchmark suites.
No external queue service — the database is the queue.
"""

import asyncio
import logging
import signal

from cortex.config import get_settings

logging.basicConfig(
    level=get_settings().log_level,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
log = logging.getLogger("cortex.worker")

POLL_INTERVAL_SECONDS = 2.0

_shutdown = asyncio.Event()


async def claim_and_run_one() -> bool:
    """Claim the oldest queued job and run it. Returns True if a job ran.

    Job handlers are registered as the pipelines land (ingestion, benchmarks).
    """
    from cortex.jobs import claim_next_job, run_job  # local import: avoids startup cycle

    import cortex.benchmark.runner  # noqa: F401 — registers the run_benchmark handler
    import cortex.ingestion.pipeline  # noqa: F401 — registers the ingest_source handler

    job = await claim_next_job(kinds=_lane_kinds())
    if job is None:
        return False
    await run_job(job)
    return True


def _lane_kinds() -> list[str] | None:
    """Job kinds this worker claims — its workload lane.

    CORTEX_WORKER_KINDS="ingest_source" gives an ingestion-only worker that
    a long benchmark can never block. Empty means claim everything.
    """
    raw = get_settings().worker_kinds.strip()
    if not raw:
        return None
    return [k.strip() for k in raw.split(",") if k.strip()]


async def main() -> None:
    from cortex.db import dispose_engine
    from cortex.jobs import heartbeat

    kinds = _lane_kinds()
    log.info("worker starting (lane=%s, poll interval %.1fs)",
             ",".join(kinds) if kinds else "*", POLL_INTERVAL_SECONDS)
    try:
        while not _shutdown.is_set():
            try:
                await heartbeat(kinds)  # liveness beacon for the health endpoint
                ran = await claim_and_run_one()
            except Exception:  # noqa: BLE001 — the loop must survive any failure
                log.exception("worker iteration failed")
                ran = False
            if not ran:
                try:
                    await asyncio.wait_for(_shutdown.wait(), timeout=POLL_INTERVAL_SECONDS)
                except TimeoutError:
                    pass
    finally:
        await dispose_engine()  # graceful shutdown: close the connection pool
        log.info("worker stopped")


def _handle_signal(*_: object) -> None:
    _shutdown.set()


if __name__ == "__main__":
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except (ValueError, OSError):  # pragma: no cover — platform quirks
            pass
    asyncio.run(main())
