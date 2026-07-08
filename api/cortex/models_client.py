"""Async client for the local model runtime (Ollama).

The rest of the codebase talks to models only through this module so the
runtime stays model-agnostic: swapping Ollama for another local runtime
means reimplementing this interface, nothing else.
"""

import httpx

from cortex.config import get_settings


class ModelUnavailableError(RuntimeError):
    """Raised when a required model is not present or the runtime is down."""


class ModelClient:
    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.model_base_url).rstrip("/")
        self._task_model = settings.task_model
        self._embed_model = settings.embed_model

    async def available_models(self) -> list[str]:
        """Names of models currently present in the runtime."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self._base_url}/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]

    async def missing_models(self) -> list[str]:
        """Required models not yet available (empty list = fully ready)."""
        try:
            present = await self.available_models()
        except httpx.HTTPError as exc:
            raise ModelUnavailableError(f"model runtime unreachable: {exc}") from exc
        required = get_settings().required_models
        # Ollama reports names with tags (e.g. "qwen2.5:3b-instruct"); match on prefix
        # so "nomic-embed-text" matches "nomic-embed-text:latest".
        return [
            r for r in required
            if not any(p == r or p.startswith(f"{r}:") for p in present)
        ]

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

        Returns {"text", "input_tokens", "output_tokens", "duration_ms"}.
        Token counts come from the runtime itself, not estimates — they feed
        benchmark metrics and must be real.
        """
        payload = {
            "model": model or self._task_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        async with httpx.AsyncClient(timeout=600) as client:
            try:
                resp = await client.post(f"{self._base_url}/api/generate", json=payload)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ModelUnavailableError(f"generation failed: {exc}") from exc
        data = resp.json()
        return {
            "text": data.get("response", ""),
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
            "duration_ms": data.get("total_duration", 0) // 1_000_000,
        }

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        """Embed a batch of texts; order of results matches input order."""
        payload = {"model": model or self._embed_model, "input": texts}
        async with httpx.AsyncClient(timeout=300) as client:
            try:
                resp = await client.post(f"{self._base_url}/api/embed", json=payload)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ModelUnavailableError(f"embedding failed: {exc}") from exc
        return resp.json().get("embeddings", [])


_client: ModelClient | None = None


def get_model_client() -> ModelClient:
    global _client
    if _client is None:
        _client = ModelClient()
    return _client
