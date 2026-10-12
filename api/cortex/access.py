"""Per-user access control.

Every repository (``source``) has an owner; versions, executions, chat
sessions, jobs and benchmark runs inherit it through their foreign keys.
Routers install :func:`guard`, which checks any resource id found in the URL
path against the authenticated user, so a new route that takes
``{version_id}`` / ``{execution_id}`` / ... is protected by default.
Not-yours and not-found are both a 404 — existence is not disclosed.
Ids that arrive in a body or query string are checked by the route itself
via :func:`version_owned`.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, Request
from sqlalchemy import text

from cortex.db import get_session_factory
from cortex.security import LOCAL_USER

_OWNED_VERSION = (
    "SELECT 1 FROM source_version v JOIN source s ON s.id = v.source_id "
    "WHERE v.id = :id AND s.owner_id = :u"
)
_CHECKS = {
    "version_id": _OWNED_VERSION,
    "execution_id": (
        "SELECT 1 FROM execution e JOIN source_version v ON v.id = e.source_version_id "
        "JOIN source s ON s.id = v.source_id WHERE e.id = :id AND s.owner_id = :u"
    ),
    "session_id": (
        "SELECT 1 FROM chat_session c JOIN source_version v ON v.id = c.source_version_id "
        "JOIN source s ON s.id = v.source_id WHERE c.id = :id AND s.owner_id = :u"
    ),
    "run_id": (
        "SELECT 1 FROM benchmark_run b JOIN source_version v ON v.id = b.source_version_id "
        "JOIN source s ON s.id = v.source_id WHERE b.id = :id AND s.owner_id = :u"
    ),
    "job_id": "SELECT 1 FROM job WHERE id = :id AND coalesce(payload->>'owner_id', 'local') = :u",
}


def user_of(request: Request) -> str:
    return getattr(request.state, "user", LOCAL_USER)


async def guard(request: Request) -> None:
    """Router dependency: 404 unless the user owns every resource id in the path."""
    user = user_of(request)
    for name, sql in _CHECKS.items():
        raw = request.path_params.get(name)
        if raw is None:
            continue
        try:
            rid = uuid.UUID(str(raw))
        except ValueError:
            continue  # the route's own validation reports a malformed id
        async with get_session_factory()() as session:
            if (await session.execute(text(sql), {"id": rid, "u": user})).first() is None:
                raise HTTPException(status_code=404, detail="not found")


async def version_owned(session, version_id: uuid.UUID, user: str) -> bool:
    return (await session.execute(
        text(_OWNED_VERSION), {"id": version_id, "u": user})).first() is not None
