"""Constructs the configured LLMProvider.

Callers should depend on this factory (or the LLMProvider interface),
never on a concrete provider class directly.
"""

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.local_provider import LocalLLMProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Build the LLMProvider configured via `settings.llm_provider`."""
    if settings.llm_provider == "local":
        if not settings.local_llm_base_url or not settings.local_llm_model:
            raise ValueError(
                "LOCAL_LLM_BASE_URL and LOCAL_LLM_MODEL must be set when "
                "LLM_PROVIDER=local"
            )
        return LocalLLMProvider(
            base_url=settings.local_llm_base_url,
            model=settings.local_llm_model,
            api_key=settings.local_llm_api_key,
            timeout_seconds=settings.local_llm_timeout_seconds,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider!r}")
