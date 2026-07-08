"""Fetch a Git repository into the ingest volume and resolve its commit."""

import hashlib
import logging
import re
import subprocess
from pathlib import Path

from cortex.config import get_settings

log = logging.getLogger("cortex.ingestion.git")


class FetchError(RuntimeError):
    pass


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise FetchError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _slug(uri: str) -> str:
    """Short, collision-safe directory name (Windows path-length friendly)."""
    tail = re.sub(r"[^a-zA-Z0-9._-]+", "-", uri.rstrip("/").split("/")[-1]).strip("-")[:40]
    digest = hashlib.sha256(uri.encode()).hexdigest()[:10]
    return f"{tail or 'repo'}-{digest}"


def fetch_repository(uri: str, ref: str | None = None) -> tuple[Path, str]:
    """Clone (or update) the repository; return (worktree_path, commit_sha).

    Local paths are supported as well as remote URLs, so a repository
    already on disk can be ingested without network access.
    """
    dest = Path(get_settings().ingest_dir) / _slug(uri)
    if (dest / ".git").exists():
        log.info("updating existing clone at %s", dest)
        _run_git(["fetch", "--all", "--tags"], cwd=dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        log.info("cloning %s -> %s", uri, dest)
        _run_git(["clone", uri, str(dest)])

    if ref:
        _run_git(["checkout", ref], cwd=dest)
    commit_sha = _run_git(["rev-parse", "HEAD"], cwd=dest)
    return dest, commit_sha
