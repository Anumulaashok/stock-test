"""Constructs the configured `FinancialDataProvider`.

`FINANCIAL_DATA_PROVIDER` selects WHICH provider implementation to use —
a provider identifier (e.g. "fmp", "indianapi"), never a URL. Each
provider's own connection details live in its own namespaced settings
(`FMP_*`, `INDIAN_API_*`, ...), so selecting one provider never requires
configuring another.

Adding a new provider means adding one entry to `_PROVIDER_BUILDERS` (and
a corresponding client/mapper/provider module) — nothing in
`FinancialDataService`, `AnalysisApplicationService`,
`AnalysisPipelineService`, or the API needs to change.

This module only reads config and instantiates a provider; it never
makes an HTTP request itself.
"""

from collections.abc import Callable

from app.core.config import Settings
from app.data.base import FinancialDataProvider
from app.data.providers.fmp import FMPProvider
from app.data.providers.fmp_client import FMPClient
from app.data.providers.indianapi import IndianAPIProvider
from app.data.providers.indianapi_client import IndianAPIClient


def _build_fmp(settings: Settings) -> FinancialDataProvider:
    if not settings.fmp_api_key:
        raise ValueError("FMP_API_KEY must be set when FINANCIAL_DATA_PROVIDER=fmp")
    client = FMPClient(
        base_url=settings.fmp_base_url,
        api_key=settings.fmp_api_key,
        connect_timeout_seconds=settings.fmp_connect_timeout_seconds,
        timeout_seconds=settings.fmp_timeout_seconds,
        max_retries=settings.fmp_max_retries,
    )
    return FMPProvider(client, annual_periods_limit=settings.fmp_annual_periods_limit)


def _build_indianapi(settings: Settings) -> FinancialDataProvider:
    if not settings.indian_api_key:
        raise ValueError("INDIAN_API_KEY must be set when FINANCIAL_DATA_PROVIDER=indianapi")
    client = IndianAPIClient(
        base_url=settings.indian_api_base_url,
        api_key=settings.indian_api_key,
        connect_timeout_seconds=settings.indian_api_connect_timeout_seconds,
        timeout_seconds=settings.indian_api_timeout_seconds,
        max_retries=settings.indian_api_max_retries,
    )
    return IndianAPIProvider(client)


# Registry: provider identifier -> builder. This is the ONLY place that
# branches on provider identity in the whole application.
_PROVIDER_BUILDERS: dict[str, Callable[[Settings], FinancialDataProvider]] = {
    "fmp": _build_fmp,
    "indianapi": _build_indianapi,
}


def get_financial_data_provider(settings: Settings) -> FinancialDataProvider:
    provider_name = settings.financial_data_provider.strip().lower()
    builder = _PROVIDER_BUILDERS.get(provider_name)
    if builder is None:
        supported = ", ".join(sorted(_PROVIDER_BUILDERS))
        raise ValueError(
            f"Unsupported FINANCIAL_DATA_PROVIDER: {settings.financial_data_provider!r}. "
            f"Supported providers: {supported}. FINANCIAL_DATA_PROVIDER must be a "
            "provider identifier, not a URL — set the provider's own base-URL setting "
            "instead (e.g. INDIAN_API_BASE_URL for indianapi, FMP_BASE_URL for fmp)."
        )
    return builder(settings)
