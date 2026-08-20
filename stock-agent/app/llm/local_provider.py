"""LLM provider that talks to a remote, OpenAI-compatible local server.

This targets a self-hosted model (e.g. Qwen3-8B served via vLLM or similar)
reachable over HTTP on another machine — the base URL, model name, API
key, and timeouts are all configuration-driven, and nothing about a
specific server or network location is hardcoded here.

The application must not assume the model is running on the same host as
this API:

    Development machine --HTTP--> {LOCAL_LLM_BASE_URL} --> Qwen3-8B
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
        connect_timeout_seconds: float = 5.0,
        timeout_seconds: float = 30.0,
        enable_thinking: bool = False,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required for LocalLLMProvider")
        if not model:
            raise ValueError("model is required for LocalLLMProvider")

        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._enable_thinking = enable_thinking
        self._timeout = httpx.Timeout(
            timeout=timeout_seconds, connect=connect_timeout_seconds
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        enable_thinking: bool | None = None,
        **kwargs: Any,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "chat_template_kwargs": {
                "enable_thinking": (
                    self._enable_thinking if enable_thinking is None else enable_thinking
                )
            },
            **kwargs,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
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
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            logger.error("Unexpected local LLM response shape: %s", exc)
            raise LLMProviderError("Unexpected local LLM response shape") from exc

        if not content or not content.strip():
            logger.error("Local LLM returned an empty response")
            raise LLMProviderError("Local LLM returned an empty response")

        return content

    async def generate_structured(self, prompt: str, schema: dict, **kwargs: Any) -> dict:
        raise NotImplementedError(
            "Structured generation is not implemented yet for LocalLLMProvider."
        )

    async def health_check(self) -> bool:
        try:
            await self.generate(
                "Reply with exactly: Remote AI connection works.",
                max_tokens=32,
                enable_thinking=False,
            )
            return True
        except LLMProviderError as exc:
            logger.warning("Local LLM health check failed: %s", exc)
            return False
