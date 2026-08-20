"""LLM provider that talks to a remote, OpenAI-compatible local server.

This targets a self-hosted model (e.g. Qwen) reachable over HTTP, using
the OpenAI-compatible `/chat/completions` endpoint convention. The base
URL, model name, and credentials are all configuration-driven — nothing
about a specific server is hardcoded here.
"""

import logging
from typing import Any

import httpx

from app.llm.base import LLMProvider, LLMProviderError

logger = logging.getLogger(__name__)


class LocalLLMProvider(LLMProvider):
    """Talks to a remote local LLM server via an OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required for LocalLLMProvider")
        if not model:
            raise ValueError("model is required for LocalLLMProvider")

        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.error("Local LLM request timed out: %s", exc)
            raise LLMProviderError("Local LLM request timed out") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Local LLM returned an error status: %s", exc.response.status_code
            )
            raise LLMProviderError(
                f"Local LLM returned status {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Local LLM request failed: %s", exc)
            raise LLMProviderError("Local LLM request failed") from exc

        try:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            logger.error("Unexpected local LLM response shape: %s", exc)
            raise LLMProviderError("Unexpected local LLM response shape") from exc

    async def generate_structured(self, prompt: str, schema: dict, **kwargs: Any) -> dict:
        raise NotImplementedError(
            "Structured generation is not implemented yet for LocalLLMProvider."
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(
                    f"{self._base_url}/models",
                    headers=self._headers(),
                )
            response.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("Local LLM health check failed: %s", exc)
            return False
