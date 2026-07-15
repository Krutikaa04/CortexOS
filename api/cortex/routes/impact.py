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
import urllib.error
import urllib.request
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

# github.com/<owner>/<repo>/pull/<n>  (also tolerates trailing /files, .diff, etc.)
_PR_URL = re.compile(
    r"github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/pull/(?P<number>\d+)", re.I
)
_GITHUB_DIFF_MAX_BYTES = 2_000_000  # guard against pathologically large PRs


class ImpactRequest(BaseModel):
    diff: str


class GitHubImpactRequest(BaseModel):
    pr_url: str


def _fetch_github_pr_diff(pr_url: str) -> str:
    """Fetch a public GitHub pull request's unified diff (zero-cost, no auth).

    Uses the REST API's ``application/vnd.github.v3.diff`` media type, which
    returns exactly the diff the Change Impact Guard already parses. Runs in a
    worker thread (blocking urllib) via ``asyncio.to_thread`` at the call site.
    """
    m = _PR_URL.search(pr_url.strip())
    if not m:
        raise ValueError(
            "expected a GitHub pull request URL like "
            "https://github.com/owner/repo/pull/123"
        )
    owner, repo, number = m["owner"], m["repo"].removesuffix(".git"), m["number"]
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    req = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github.v3.diff",
            "User-Agent": "CortexOS-ChangeImpactGuard",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read(_GITHUB_DIFF_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError("pull request not found (or the repository is private)")
        if exc.code in (403, 429):
            raise ValueError("GitHub rate limit reached — try again shortly")
        raise ValueError(f"GitHub returned HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(f"could not reach GitHub: {exc}")
    if len(raw) > _GITHUB_DIFF_MAX_BYTES:
        raise ValueError("pull request diff is too large to analyze")
    return raw.decode("utf-8", errors="replace")


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


@router.get("/{version_id}/impact/history")
async def impact_history(
    version_id: uuid.UUID,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Past Change Impact Guard analyses for a repository version.

    Impact runs are already persisted as executions (mode='impact') with the
    full report in ``metrics`` — this reuses that storage rather than adding a
    parallel table, so a reviewer can revisit any prior analysis and its
    verdict without re-running it.
    """
    rows = (
        await session.execute(
            text(
                "SELECT id, query, answer, status, metrics, started_at, finished_at "
                "FROM execution WHERE source_version_id = :vid AND mode = 'impact' "
                "ORDER BY started_at DESC LIMIT :limit"
            ),
            {"vid": version_id, "limit": min(limit, 100)},
        )
    ).all()
    out: list[dict] = []
    for r in rows:
        m = r.metrics or {}
        out.append({
            "id": str(r.id),
            "label": r.query,
            "status": r.status,
            "risk_level": m.get("risk_level"),
            "confidence": m.get("confidence"),
            "changed_files": m.get("changed_files") or [],
            "summary": m.get("summary") or r.answer,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        })
    return out


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


@router.post("/{version_id}/impact/github", status_code=202)
async def analyze_github_pr(
    version_id: uuid.UUID,
    body: GitHubImpactRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Fetch a public GitHub PR's diff and run the same Change Impact Guard.

    This reuses the entire impact pipeline — the only new work is resolving a
    PR URL to its diff, so a reviewer can point CortexOS at a real pull request
    instead of pasting a patch by hand.
    """
    ready = (
        await session.execute(
            text("SELECT 1 FROM source_version WHERE id = :id AND status = 'ready'"),
            {"id": version_id},
        )
    ).first()
    if ready is None:
        raise HTTPException(status_code=404, detail="source version not found or not ready")

    try:
        diff = await asyncio.to_thread(_fetch_github_pr_diff, body.pr_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not diff.strip():
        raise HTTPException(status_code=422, detail="pull request has no diff to analyze")

    execution_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO execution (id, source_version_id, mode, query, status) "
            "VALUES (:id, :vid, 'impact', :q, 'running')"
        ),
        {"id": execution_id, "vid": version_id, "q": _label(diff)},
    )
    await session.commit()

    asyncio.create_task(_run_impact(execution_id, version_id, diff))
    return {"execution_id": str(execution_id), "status": "running"}
