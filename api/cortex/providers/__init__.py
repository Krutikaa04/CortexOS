"""Model provider abstraction.

The runtime talks to language/embedding models only through the
``ModelProvider`` interface, so the deployment target chooses an
implementation by configuration (``CORTEX_MODEL_PROVIDER``) without any
business-logic change. Local Ollama is the default and only bundled
implementation — remote/hosted providers can be added here later without
touching the Kernel.
"""

from __future__ import annotations

import logging

from cortex.config import get_settings
from cortex.providers.base import ModelProvider, ModelUnavailableError
from cortex.providers.ollama import OllamaProvider

log = logging.getLogger("cortex.providers")

# name -> factory. Add future providers (openai, gemini, vllm, lmstudio) here;
# each only needs to implement ModelProvider.
_REGISTRY: dict[str, type[ModelProvider]] = {
    "ollama": OllamaProvider,
}

_provider: ModelProvider | None = None


def get_provider() -> ModelProvider:
    """Return the configured process-wide model provider (lazy singleton)."""
    global _provider
    if _provider is None:
        name = get_settings().model_provider.strip().lower()
        impl = _REGISTRY.get(name)
        if impl is None:
            raise ModelUnavailableError(
                f"unknown model provider {name!r}; supported: {', '.join(sorted(_REGISTRY))}"
            )
        _provider = impl()
        log.info("model provider: %s", name)
    return _provider


def reset_provider() -> None:
    """Drop the cached provider (tests / config reloads)."""
    global _provider
    _provider = None


__all__ = ["ModelProvider", "ModelUnavailableError", "get_provider", "reset_provider"]
