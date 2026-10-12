"""User accounts: registration, password login and revocable session tokens.

- Passwords are hashed with scrypt (stdlib) and a per-user random salt; the
  plaintext is never stored or logged.
- A login returns an opaque random session token. Only its SHA-256 is stored,
  so a database leak does not yield usable tokens; sessions expire and can be
  revoked (logout).
- A user's id is the ``owner_id`` of everything they create, so the existing
  ownership guard isolates accounts with no further changes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time
import uuid

from sqlalchemy import text

from cortex.config import get_settings
from cortex.db import get_session_factory

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
MIN_PASSWORD = 8
MAX_PASSWORD = 256
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}

# Failed-login throttle (per process; adequate for the single API replica).
_FAILS: dict[str, list[float]] = {}
MAX_FAILS = 8
FAIL_WINDOW = 15 * 60


class AccountError(ValueError):
    """Raised with a message that is safe to show the user."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT, dklen=32)
    return "scrypt$%d$%d$%d$%s$%s" % (
        _SCRYPT["n"], _SCRYPT["r"], _SCRYPT["p"],
        base64.b64encode(salt).decode(), base64.b64encode(dk).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                             n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


# A real hash to compare against when the email is unknown, so a login for a
# missing account takes as long as one for an existing account.
_DUMMY = hash_password("not-a-real-password")


def normalize_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not _EMAIL.match(e):
        raise AccountError("enter a valid email address")
    return e


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AccountError(f"password must be at least {MIN_PASSWORD} characters")
    if len(password) > MAX_PASSWORD:
        raise AccountError("password is too long")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _new_session(session, user_id: uuid.UUID) -> str:
    token = secrets.token_urlsafe(32)
    days = get_settings().session_days
    await session.execute(
        text("INSERT INTO user_session (token_hash, user_id, expires_at) "
             "VALUES (:h, :u, now() + make_interval(days => :d))"),
        {"h": _token_hash(token), "u": user_id, "d": days},
    )
    await session.execute(text("DELETE FROM user_session WHERE expires_at < now()"))
    return token


async def _claim_local(session, email: str, user_id: uuid.UUID) -> None:
    """The admin-designated account (CORTEX_LOCAL_OWNER_EMAIL) adopts the
    repositories ingested before accounts existed."""
    owner = get_settings().local_owner_email.strip().lower()
    if owner and owner == email:
        await session.execute(
            text("UPDATE source SET owner_id = :u WHERE owner_id = 'local'"),
            {"u": str(user_id)},
        )


async def register(email: str, password: str, display_name: str | None) -> tuple[dict, str]:
    if not get_settings().registration_open:
        raise AccountError("registration is closed", 403)
    email = normalize_email(email)
    _check_password(password)
    name = (display_name or email.split("@")[0]).strip()[:64] or "user"
    uid = uuid.uuid4()
    pw = hash_password(password)
    async with get_session_factory()() as session:
        exists = (await session.execute(
            text("SELECT 1 FROM app_user WHERE email = :e"), {"e": email})).first()
        if exists:
            raise AccountError("an account with this email already exists", 409)
        await session.execute(
            text("INSERT INTO app_user (id, email, display_name, password_hash) "
                 "VALUES (:id, :e, :n, :p)"),
            {"id": uid, "e": email, "n": name, "p": pw},
        )
        await _claim_local(session, email, uid)
        token = await _new_session(session, uid)
        await session.commit()
    return {"id": str(uid), "email": email, "display_name": name}, token


def _throttled(key: str) -> bool:
    now = time.time()
    recent = [t for t in _FAILS.get(key, []) if now - t < FAIL_WINDOW]
    _FAILS[key] = recent
    return len(recent) >= MAX_FAILS


async def login(email: str, password: str, client: str = "") -> tuple[dict, str]:
    email_n = (email or "").strip().lower()
    keys = [f"e:{email_n}", f"c:{client}"] if client else [f"e:{email_n}"]
    if any(_throttled(k) for k in keys):
        raise AccountError("too many failed attempts; try again in a few minutes", 429)
    async with get_session_factory()() as session:
        row = (await session.execute(
            text("SELECT id, email, display_name, password_hash FROM app_user "
                 "WHERE email = :e"), {"e": email_n})).first()
        ok = verify_password(password or "", row.password_hash if row else _DUMMY)
        if not (row and ok):
            now = time.time()
            for k in keys:
                _FAILS.setdefault(k, []).append(now)
            raise AccountError("incorrect email or password", 401)
        for k in keys:
            _FAILS.pop(k, None)
        await _claim_local(session, row.email, row.id)
        token = await _new_session(session, row.id)
        await session.commit()
    return {"id": str(row.id), "email": row.email, "display_name": row.display_name}, token


async def user_for_token(token: str) -> dict | None:
    if not token:
        return None
    async with get_session_factory()() as session:
        row = (await session.execute(
            text("SELECT u.id, u.email, u.display_name FROM user_session s "
                 "JOIN app_user u ON u.id = s.user_id "
                 "WHERE s.token_hash = :h AND s.expires_at > now()"),
            {"h": _token_hash(token)})).first()
    if row is None:
        return None
    return {"id": str(row.id), "email": row.email, "display_name": row.display_name}


async def revoke(token: str) -> None:
    async with get_session_factory()() as session:
        await session.execute(text("DELETE FROM user_session WHERE token_hash = :h"),
                              {"h": _token_hash(token)})
        await session.commit()
