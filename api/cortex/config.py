"""Environment configuration.

Validated at import time by the API and the worker; the process refuses
to start with an unreadable configuration rather than run misconfigured.

One codebase serves both local Docker development and cloud production —
the only difference is environment variables. Nothing here assumes Docker
networking; every host/URL is overridable.
"""

import re
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

# libpq query params that asyncpg does not understand and must be stripped
# from a connection URL (their intent is translated into connect_args).
_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding", "gssencmode", "target_session_attrs"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CORTEX_", extra="ignore")

    # Accepts either a SQLAlchemy async URL or a plain managed-Postgres URL
    # ('postgres://…' / 'postgresql://…'); normalized in `async_db_url`.
    db_url: str = "postgresql+asyncpg://cortex:change-me@cortex-db:5432/cortex"
    # Force TLS to the database regardless of URL params (managed Postgres).
    # "auto" = infer from the URL's sslmode; "true"/"false" force it.
    db_ssl: str = "auto"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # --- Model provider ---
    model_provider: str = "ollama"
    model_base_url: str = "http://cortex-model:11434"
    model_connect_timeout: float = 10.0
    model_generate_timeout: float = 600.0
    model_embed_timeout: float = 300.0
    model_max_retries: int = 1

    task_model: str = "qwen2.5:3b-instruct"
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768

    env: str = "dev"
    log_level: str = "INFO"
    api_token: str = ""

    # CORS: comma-separated exact origins allowed to call the API from a
    # browser (e.g. the Vercel Studio URL). In dev, empty means "reflect any
    # origin" for convenience; in production, empty means "same-origin only".
    allowed_origins: str = ""

    # Token for cloning PRIVATE https git repositories (e.g. a GitHub PAT).
    # Supplied only via secure configuration (CORTEX_GIT_TOKEN); never logged,
    # never returned by the API. Empty = public repositories only.
    git_token: str = ""

    # Comma-separated job kinds this worker claims (its workload lane).
    # Empty = claim every registered kind (single-worker dev setups).
    worker_kinds: str = ""

    # Model used for internal structured steps (e.g. requirement generation).
    # Defaults to the task model; point it at a smaller local model to speed
    # up internal reasoning without touching answer quality.
    internal_model: str = ""

    # Ingestion workspace. A writable path (a mounted disk in production, a
    # named volume in Docker, a temp dir on ephemeral hosts).
    ingest_dir: str = "/data/ingest"
    # Delete a repo's clone after ingestion finishes (keeps ephemeral disks
    # small). Off by default so re-ingest of the same commit stays fast.
    ingest_cleanup: bool = False

    @property
    def is_production(self) -> bool:
        return self.env.lower() in ("prod", "production")

    @property
    def required_models(self) -> list[str]:
        return [self.task_model, self.embed_model]

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def async_db_url(self) -> str:
        """SQLAlchemy asyncpg URL, normalized from any accepted input form.

        Managed providers hand out 'postgres://user:pass@host/db?sslmode=require';
        this rewrites the scheme to 'postgresql+asyncpg' and strips libpq-only
        query params asyncpg rejects (their meaning is applied via connect_args).
        """
        url = self.db_url
        url = re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", url)
        parts = urlsplit(url)
        kept = [(k, v) for k, v in parse_qsl(parts.query) if k not in _LIBPQ_ONLY_PARAMS]
        return urlunsplit(parts._replace(query=urlencode(kept)))

    @property
    def db_connect_args(self) -> dict:
        """asyncpg connect_args, notably TLS for managed Postgres."""
        setting = self.db_ssl.lower()
        if setting == "true":
            return {"ssl": True}
        if setting == "false":
            return {}
        # auto: enable TLS when the URL asked for it, or in production against
        # a non-local host (managed Postgres effectively always requires TLS).
        query = dict(parse_qsl(urlsplit(self.db_url).query))
        sslmode = query.get("sslmode", "")
        if sslmode and sslmode not in ("disable", "allow"):
            return {"ssl": True}
        host = urlsplit(self.async_db_url).hostname or ""
        if self.is_production and host not in ("localhost", "127.0.0.1", "cortex-db"):
            return {"ssl": True}
        return {}


@lru_cache
def get_settings() -> Settings:
    return Settings()
