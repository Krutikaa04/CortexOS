"""Model provider interface shared by every implementation."""

from __future__ import annotations

import abc


class ModelUnavailableError(RuntimeError):
    """Raised when a required model is not present or the provider is down."""


class ModelProvider(abc.ABC):
    """Async interface for text generation + embeddings.

    Implementations must not leak provider-specific types: callers depend only
    on the shapes documented here so the rest of the runtime stays
    provider-agnostic.
    """

    #: short, stable identifier surfaced in health/metrics (e.g. "ollama")
    name: str = "unknown"

    @abc.abstractmethod
    async def available_models(self) -> list[str]:
        """Names of models the provider currently has ready."""

    @abc.abstractmethod
    async def missing_models(self) -> list[str]:
        """Required models that are not yet ready (empty = fully ready).

        Raises ModelUnavailableError if the provider itself is unreachable.
        """

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> dict:
        """Single non-streaming completion.

        Returns {"text", "input_tokens", "output_tokens", "duration_ms"} with
        real token counts from the provider (they feed benchmark metrics).
        """

    @abc.abstractmethod
    async def embed(
        self, texts: list[str], *, model: str | None = None
    ) -> list[list[float]]:
        """Embed a batch; result order matches input order."""
