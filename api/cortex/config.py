"""Environment configuration.

Validated at import time by the API and the worker; the process refuses
to start with an unreadable configuration rather than run misconfigured.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CORTEX_", extra="ignore")

    db_url: str = "postgresql+asyncpg://cortex:change-me@cortex-db:5432/cortex"
    model_base_url: str = "http://cortex-model:11434"

    task_model: str = "qwen2.5:3b-instruct"
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768

    env: str = "dev"
    log_level: str = "INFO"
    api_token: str = ""

    # Comma-separated job kinds this worker claims (its workload lane).
    # Empty = claim every registered kind (single-worker dev setups).
    worker_kinds: str = ""

    # Model used for internal structured steps (e.g. requirement generation).
    # Defaults to the task model; point it at a smaller local model to speed
    # up internal reasoning without touching answer quality.
    internal_model: str = ""

    ingest_dir: str = "/data/ingest"

    @property
    def required_models(self) -> list[str]:
        return [self.task_model, self.embed_model]


@lru_cache
def get_settings() -> Settings:
    return Settings()
