"""Model access facade.

Historically this module *was* the Ollama client. It is now a thin,
backwards-compatible facade over the provider abstraction in
``cortex.providers`` so existing imports keep working while the concrete
runtime is chosen by configuration (``CORTEX_MODEL_PROVIDER``).
"""

from cortex.providers import get_provider
from cortex.providers.base import ModelProvider, ModelUnavailableError
from cortex.providers.ollama import OllamaProvider

# Backwards-compatible alias: earlier code referred to the concrete client.
ModelClient = OllamaProvider


def get_model_client() -> ModelProvider:
    """Return the configured model provider (single process-wide instance)."""
    return get_provider()


__all__ = ["ModelClient", "ModelProvider", "ModelUnavailableError", "get_model_client"]
