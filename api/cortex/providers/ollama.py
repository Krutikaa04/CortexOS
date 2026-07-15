"""Ollama model provider — the default, zero-cost local implementation.

Only this module knows the runtime is Ollama; everything else depends on the
``ModelProvider`` interface. The base URL is configuration-driven
(``CORTEX_MODEL_BASE_URL``), so the same code talks to Ollama inside local
Docker or to an Ollama reachable over the network in a cloud deployment.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from cortex.config import get_settings
from cortex.providers.base import ModelProvider, ModelUnavailableError

log = logging.getLogger("cortex.providers.ollama")


class OllamaProvider(ModelProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.model_base_url).rstrip("/")
        self._task_model = settings.task_model
        self._embed_model = settings.embed_model
        self._connect_timeout = settings.model_connect_timeout
        self._generate_timeout = settings.model_generate_timeout
        self._embed_timeout = settings.model_embed_timeout
        self._retries = settings.model_max_retries

    async def _post(self, path: str, payload: dict, timeout: float) -> dict:
        """POST with a bounded retry on transient network/5xx errors.

        Generation/embedding are idempotent for our purposes (no side effects),
        so a short retry smooths over a provider that is briefly overloaded or
        still warming a model, without masking a real outage.
        """
        last: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout, connect=self._connect_timeout)
                ) as client:
                    resp = await client.post(f"{self._base_url}{path}", json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as exc:
                # 4xx (bad request/model missing) is not retryable
                if exc.response.status_code < 500:
                    raise ModelUnavailableError(f"{path} failed: {exc}") from exc
                last = exc
            except httpx.HTTPError as exc:
                last = exc
            if attempt < self._retries:
                await asyncio.sleep(0.5 * (attempt + 1))
        raise ModelUnavailableError(f"{path} failed after retries: {last}") from last

    async def available_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10, connect=self._connect_timeout)
            ) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                resp.raise_for_status()
                return [m["name"] for m in resp.json().get("models", [])]
        except httpx.HTTPError as exc:
            raise ModelUnavailableError(f"model runtime unreachable: {exc}") from exc

    async def missing_models(self) -> list[str]:
        present = await self.available_models()
        required = get_settings().required_models
        # Ollama reports tagged names ("qwen2.5:3b-instruct"); match on prefix
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
        payload: dict = {
            "model": model or self._task_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        data = await self._post("/api/generate", payload, self._generate_timeout)
        return {
            "text": data.get("response", ""),
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
            "duration_ms": data.get("total_duration", 0) // 1_000_000,
        }

    async def embed(
        self, texts: list[str], *, model: str | None = None
    ) -> list[list[float]]:
        payload = {"model": model or self._embed_model, "input": texts}
        data = await self._post("/api/embed", payload, self._embed_timeout)
        return data.get("embeddings", [])
