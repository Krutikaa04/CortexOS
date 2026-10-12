"""Input validation and auth helpers (production hardening).

Centralizes the checks that protect the two sensitive surfaces: the git
subprocess (repository cloning) and the API's authentication gate. Kept as
pure functions so they are unit-testable without a server.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import urlsplit

from cortex.config import get_settings

# git remotes we accept as clearly-remote sources.
_REMOTE_URI = re.compile(r"^(https?://|git://|ssh://|git@[\w.-]+:)", re.I)
# a ref/branch/tag/sha — no option-injection, no whitespace, no shell metachars.
_SAFE_REF = re.compile(r"^[\w./\-]{1,200}$")


class ValidationError(ValueError):
    """Raised when untrusted input fails a security check."""


def validate_repo_uri(uri: str, *, allow_local: bool | None = None) -> str:
    """Validate a repository URI before it reaches ``git clone``.

    Blocks argument injection (a URI parsed by git as an option), ``file://``
    disclosure, and — in production — local filesystem paths. Local paths stay
    allowed in development so an on-disk repo can be ingested offline.
    """
    if allow_local is None:
        allow_local = not get_settings().is_production
    s = (uri or "").strip()
    if not s:
        raise ValidationError("repository URI is required")
    if s.startswith("-"):
        raise ValidationError("invalid repository URI")  # git option injection
    if any(ch in s for ch in "\n\r\t") or " " in s:
        raise ValidationError("repository URI contains invalid characters")
    if s.lower().startswith("file://"):
        raise ValidationError("file:// URIs are not allowed")
    if _REMOTE_URI.match(s):
        if get_settings().is_production:
            # Public deployment: https to an allow-listed git host only. Blocks
            # SSRF to internal addresses and non-https transports.
            parts = urlsplit(s)
            if parts.scheme.lower() != "https" or parts.username or parts.password:
                raise ValidationError("only credential-free https repository URLs are allowed")
            if (parts.hostname or "").lower() not in get_settings().git_allowed_hosts_list:
                raise ValidationError("repository host is not allowed")
        return s
    # not a recognized remote → treat as a local path
    if not allow_local:
        raise ValidationError("only remote git URIs are allowed in production")
    if ".." in s.replace("\\", "/").split("/"):
        raise ValidationError("path traversal is not allowed")
    return s


def validate_git_ref(ref: str | None) -> str | None:
    """Validate an optional git ref before it reaches ``git checkout``."""
    if ref is None:
        return None
    s = ref.strip()
    if not s:
        return None
    if s.startswith("-") or not _SAFE_REF.match(s):
        raise ValidationError("invalid git ref")
    return s


def check_api_token(authorization: str | None) -> bool:
    """True when the request is authorized.

    Auth is enforced only when ``CORTEX_API_TOKEN`` is configured; empty token
    means open access (local development). Constant-shape bearer check.
    """
    return authenticate(authorization) is not None


# ---------------------------------------------------------------------------
# Identity: bearer token -> user id
# ---------------------------------------------------------------------------

LOCAL_USER = "local"  # open dev mode, and the owner of pre-ownership rows
_PROCESS_SECRET = secrets.token_hex(32)
_USER_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def token_users() -> dict[str, str]:
    """token -> user id from ``CORTEX_API_TOKENS`` ("alice:tok1,bob:tok2").

    The legacy single ``CORTEX_API_TOKEN`` maps to the ``local`` user so an
    existing deployment keeps seeing the repositories it already ingested.
    Malformed entries are ignored rather than silently granting access.
    """
    s = get_settings()
    out: dict[str, str] = {}
    for item in s.api_tokens.split(","):
        user, sep, token = item.strip().partition(":")
        if sep and token and _USER_ID.match(user):
            out[token] = user
    if s.api_token:
        out.setdefault(s.api_token, LOCAL_USER)
    return out


def authenticate(authorization: str | None) -> str | None:
    """Return the user id for a request's bearer token, or None if rejected.

    With no tokens configured the API is open (local development) and every
    request is the ``local`` user. Comparison is constant-time per token.
    """
    users = token_users()
    if not users:
        return LOCAL_USER
    if not authorization:
        return None
    scheme, _, presented = authorization.partition(" ")
    if scheme.lower() != "bearer" or not presented:
        return None
    found = None
    for token, user in users.items():  # no early exit: timing independent of match
        if hmac.compare_digest(token.encode(), presented.encode()):
            found = user
    return found


def _ticket_key() -> bytes:
    s = get_settings()
    material = s.secret_key or _PROCESS_SECRET
    return hashlib.sha256(("cortex-stream:" + material).encode()).digest()


def make_stream_ticket(execution_id: str, user: str, ttl: int = 120) -> str:
    """Short-lived, execution-bound ticket for the SSE stream (EventSource
    cannot send an Authorization header, and tokens must not go in URLs)."""
    exp = int(time.time()) + ttl
    body = f"{execution_id}.{user}.{exp}"
    sig = hmac.new(_ticket_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_stream_ticket(ticket: str, execution_id: str) -> str | None:
    """User id when the ticket is authentic, unexpired and for this execution."""
    try:
        body, sig = ticket.rsplit(".", 1)
        exec_id, user, exp = body.split(".", 2)
    except ValueError:
        return None
    good = hmac.new(_ticket_key(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, sig) or exec_id != execution_id:
        return None
    try:
        return user if int(exp) >= time.time() else None
    except ValueError:
        return None
