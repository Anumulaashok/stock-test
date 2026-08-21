"""Constructs the configured `ResearchProvider`. Mirrors
`app.data.factory.get_financial_data_provider`."""

from app.core.config import Settings
from app.research.base import ResearchProvider
from app.research.providers.finnhub import FinnhubProvider
from app.research.providers.finnhub_client import FinnhubClient


def get_research_provider(settings: Settings) -> ResearchProvider:
    if settings.research_provider == "finnhub":
        if not settings.research_api_key:
            raise ValueError("RESEARCH_API_KEY must be set when RESEARCH_PROVIDER=finnhub")
        client = FinnhubClient(
            base_url=settings.research_base_url,
            api_key=settings.research_api_key,
            connect_timeout_seconds=settings.research_connect_timeout_seconds,
            timeout_seconds=settings.research_timeout_seconds,
            max_retries=settings.research_max_retries,
        )
        return FinnhubProvider(client, default_date_range_days=settings.research_default_days)

    raise ValueError(f"Unsupported RESEARCH_PROVIDER: {settings.research_provider!r}")
