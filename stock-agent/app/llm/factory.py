"""Constructs the configured LLMProvider.

Callers should depend on this factory (or the LLMProvider interface),
never on a concrete provider class directly.
"""

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.local_provider import LocalLLMProvider


_OPENAI_COMPATIBLE_PROVIDERS = {"local", "nvidia"}


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Build the LLMProvider configured via `settings.llm_provider`.

    "nvidia" is accepted as an alias of "local": NVIDIA's hosted API
    (integrate.api.nvidia.com) speaks the same OpenAI-compatible
    chat-completions protocol as any other LOCAL_LLM_BASE_URL target, so
    it's served by the same LocalLLMProvider rather than a separate
    implementation.
    """
    if settings.llm_provider in _OPENAI_COMPATIBLE_PROVIDERS:
        if not settings.local_llm_base_url or not settings.local_llm_model:
            raise ValueError(
                "LOCAL_LLM_BASE_URL and LOCAL_LLM_MODEL must be set when "
                f"LLM_PROVIDER={settings.llm_provider}"
            )
        return LocalLLMProvider(
            base_url=settings.local_llm_base_url,
            model=settings.local_llm_model,
            api_key=settings.local_llm_api_key,
            connect_timeout_seconds=settings.local_llm_connect_timeout_seconds,
            timeout_seconds=settings.local_llm_timeout_seconds,
            enable_thinking=settings.local_llm_enable_thinking,
            reasoning_mode=settings.local_llm_reasoning_mode,
            reasoning_effort=settings.local_llm_reasoning_effort,
            json_mode=settings.local_llm_json_mode,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider!r}")
