"""Health check endpoints."""

import logging

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.llm.base import LLMProviderError
from app.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


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

    try:
        reachable = await provider.health_check()
    except LLMProviderError as exc:
        logger.error("LLM health check raised an error: %s", exc)
        return {"status": "unreachable", "detail": str(exc)}

    return {
        "status": "ok" if reachable else "unreachable",
        "provider": settings.llm_provider,
        "model": settings.local_llm_model,
    }
