"""Input validation and auth helpers (production hardening).

Centralizes the checks that protect the two sensitive surfaces: the git
subprocess (repository cloning) and the API's authentication gate. Kept as
pure functions so they are unit-testable without a server.
"""

from __future__ import annotations

import re
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
    token = get_settings().api_token
    if not token:
        return True
    if not authorization:
        return False
    parts = authorization.split(" ", 1)
    return len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == token
