"""Constructs the configured `FinancialDataProvider`.

Mirrors `app.llm.factory.get_llm_provider` — callers should depend on
this factory (or the `FinancialDataProvider` interface), never on a
concrete provider class directly.
"""

from app.core.config import Settings
from app.data.base import FinancialDataProvider
from app.data.providers.fmp import FMPProvider
from app.data.providers.fmp_client import FMPClient


def get_financial_data_provider(settings: Settings) -> FinancialDataProvider:
    if settings.financial_data_provider == "fmp":
        if not settings.financial_data_api_key:
            raise ValueError(
                "FINANCIAL_DATA_API_KEY must be set when FINANCIAL_DATA_PROVIDER=fmp"
            )
        client = FMPClient(
            base_url=settings.financial_data_base_url,
            api_key=settings.financial_data_api_key,
            connect_timeout_seconds=settings.financial_data_connect_timeout_seconds,
            timeout_seconds=settings.financial_data_timeout_seconds,
            max_retries=settings.financial_data_max_retries,
        )
        return FMPProvider(client, annual_periods_limit=settings.financial_data_annual_periods_limit)

    raise ValueError(f"Unsupported FINANCIAL_DATA_PROVIDER: {settings.financial_data_provider!r}")
