"""Constructs the configured `MarketDataProvider`. Mirrors
`app.data.factory.get_financial_data_provider` — registry-based dispatch
on `MARKET_DATA_PROVIDER`, so adding a provider means adding one entry.

"fmp" reuses the existing `FMP_*` connection settings (same vendor
account already configured for financial statements) but goes through a
completely separate client/mapper/provider — see `app/market/`.
"""

from collections.abc import Callable

from app.core.config import Settings
from app.data.providers.indianapi_client import IndianAPIClient
from app.market.base import MarketDataProvider
from app.market.providers.fmp import FMPMarketProvider
from app.market.providers.fmp_client import FMPMarketClient
from app.market.providers.indianapi import IndianAPIMarketProvider


def _build_fmp(settings: Settings) -> MarketDataProvider:
    if not settings.fmp_api_key:
        raise ValueError("FMP_API_KEY must be set when MARKET_DATA_PROVIDER=fmp")
    client = FMPMarketClient(
        base_url=settings.fmp_base_url,
        api_key=settings.fmp_api_key,
        connect_timeout_seconds=settings.market_data_connect_timeout_seconds,
        timeout_seconds=settings.market_data_timeout_seconds,
        max_retries=settings.market_data_max_retries,
    )
    return FMPMarketProvider(client)


def _build_indianapi(settings: Settings) -> MarketDataProvider:
    if not settings.indian_api_key:
        raise ValueError("INDIAN_API_KEY must be set when MARKET_DATA_PROVIDER=indianapi")
    client = IndianAPIClient(
        base_url=settings.indian_api_base_url,
        api_key=settings.indian_api_key,
        connect_timeout_seconds=settings.indian_api_connect_timeout_seconds,
        timeout_seconds=settings.indian_api_timeout_seconds,
        max_retries=settings.indian_api_max_retries,
    )
    return IndianAPIMarketProvider(client)


_PROVIDER_BUILDERS: dict[str, Callable[[Settings], MarketDataProvider]] = {
    "fmp": _build_fmp,
    "indianapi": _build_indianapi,
}


def get_market_data_provider(settings: Settings) -> MarketDataProvider:
    provider_name = settings.market_data_provider.strip().lower()
    builder = _PROVIDER_BUILDERS.get(provider_name)
    if builder is None:
        supported = ", ".join(sorted(_PROVIDER_BUILDERS))
        raise ValueError(
            f"Unsupported MARKET_DATA_PROVIDER: {settings.market_data_provider!r}. "
            f"Supported providers: {supported}."
        )
    return builder(settings)
