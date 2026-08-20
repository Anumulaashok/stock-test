"""Health check endpoints."""

import logging

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.llm.base import LLMProviderError
from app.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# Minimal prompt used only to verify end-to-end connectivity to the
# remote LLM server (DNS/network, auth, and a valid completion).
LLM_CONNECTIVITY_TEST_PROMPT = "Reply with exactly: Remote AI connection works."


@router.get("")
async def health() -> dict:
    """Basic liveness check — confirms the API process is running."""
    return {"status": "ok"}


@router.get("/llm")
async def health_llm(settings: Settings = Depends(get_settings)) -> dict:
    """Verify the configured local LLM server can be reached.

    Never returns secrets (API keys, etc.) — only provider/model identity
    and reachability status.
    """
    try:
        provider = get_llm_provider(settings)
    except ValueError as exc:
        logger.warning("LLM provider misconfigured: %s", exc)
        return {"status": "misconfigured", "detail": str(exc)}

    # Enable_thinking is forced off here regardless of configuration —
    # this endpoint only needs to confirm connectivity, not reasoning.
    try:
        content = await provider.generate(
            LLM_CONNECTIVITY_TEST_PROMPT,
            max_tokens=32,
            enable_thinking=False,
        )
    except LLMProviderError as exc:
        logger.error("LLM connectivity test failed: %s", exc)
        return {
            "status": "unreachable",
            "provider": settings.llm_provider,
            "model": settings.local_llm_model,
        }

    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "model": settings.local_llm_model,
        "response": content,
    }
