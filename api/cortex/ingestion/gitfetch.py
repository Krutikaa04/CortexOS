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


def _scrub(text: str) -> str:
    """Remove any embedded git credentials from text before it is logged or
    surfaced (e.g. in a job's failure_reason)."""
    return re.sub(r"(https://)[^/@\s]+@", r"\1", text)


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        # never leak an embedded token into the exception / failure_reason
        raise FetchError(_scrub(f"git {' '.join(args)} failed: {result.stderr.strip()}"))
    return result.stdout.strip()


def _slug(uri: str) -> str:
    """Short, collision-safe directory name (Windows path-length friendly)."""
    tail = re.sub(r"[^a-zA-Z0-9._-]+", "-", uri.rstrip("/").split("/")[-1]).strip("-")[:40]
    digest = hashlib.sha256(uri.encode()).hexdigest()[:10]
    return f"{tail or 'repo'}-{digest}"


def _authenticated_uri(uri: str) -> str:
    """Inject the configured git token into an https remote for private repos.

    The token comes only from secure configuration (``CORTEX_GIT_TOKEN``),
    never from the request or the code, and is applied only to https hosts
    that don't already carry credentials. The returned URL is passed to git
    but never logged — callers log the original ``uri``. Public repositories
    keep working unchanged whether or not a token is set.
    """
    token = get_settings().git_token
    if not token or not uri.startswith("https://") or "@" in uri.split("://", 1)[1]:
        return uri
    host_and_path = uri.split("://", 1)[1]
    # 'x-access-token' works for GitHub PATs; GitLab/Bitbucket accept it too
    # as the username with the token as password.
    return f"https://x-access-token:{token}@{host_and_path}"


def fetch_repository(uri: str, ref: str | None = None) -> tuple[Path, str]:
    """Clone (or update) the repository; return (worktree_path, commit_sha).

    Local paths are supported as well as remote URLs, so a repository
    already on disk can be ingested without network access. Private https
    repositories are supported via a securely configured git token.
    """
    dest = Path(get_settings().ingest_dir) / _slug(uri)
    auth_uri = _authenticated_uri(uri)
    if (dest / ".git").exists():
        log.info("updating existing clone at %s", dest)
        # Use an explicit authenticated remote URL so a rotated token or a
        # newly-private repo keeps working without persisting the secret.
        _run_git(["fetch", "--all", "--tags", auth_uri] if auth_uri != uri
                 else ["fetch", "--all", "--tags"], cwd=dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        log.info("cloning %s -> %s", uri, dest)  # original uri only — never the token
        _run_git(["clone", auth_uri, str(dest)])

    if ref:
        _run_git(["checkout", ref], cwd=dest)
    commit_sha = _run_git(["rev-parse", "HEAD"], cwd=dest)
    return dest, commit_sha
