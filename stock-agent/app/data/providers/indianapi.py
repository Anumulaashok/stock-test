"""IndianAPIProvider: implements `FinancialDataProvider` for stock.indianapi.in.

Combines `IndianAPIClient` (HTTP) and `app.data.mappers.indianapi` (schema
mapping) so IndianAPI's field names (`NetIncome`, `TotalDebt`, `Cash`,
...) never leak past this module — everything downstream only sees
`CompanyFinancials`.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from app.data.base import FinancialDataProvider
from app.data.exceptions import ProviderError
from app.data.mappers.indianapi import build_company_financials
from app.data.models import (
    CompanyIdentifier,
    FinancialDataErrorCode,
    FinancialDataMetadata,
    FinancialDataResult,
)
from app.data.providers.indianapi_client import IndianAPIClient

logger = logging.getLogger(__name__)


class IndianAPIProvider(FinancialDataProvider):
    def __init__(
        self, client: IndianAPIClient, clock: Callable[[], datetime] | None = None
    ) -> None:
        self._client = client
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataResult:
        ticker = identifier.ticker

        # This provider is name-search based (see IndianAPIClient) — our
        # canonical `ticker` identifier is passed through as the search
        # term; that mapping is entirely internal to this provider.
        raw = await self._client.get_stock(ticker)

        financials_raw = raw.get("financials")
        if not isinstance(financials_raw, list):
            raise ProviderError(
                FinancialDataErrorCode.SCHEMA_MISMATCH,
                "financial data provider response did not include a 'financials' list",
            )

        company_name = raw.get("companyName")
        if not isinstance(company_name, str) or not company_name.strip():
            company_name = ticker

        company_financials, currency, warnings = build_company_financials(
            company_name=company_name, ticker=ticker, financials_raw=financials_raw
        )

        if (
            not company_financials.income_statements
            and not company_financials.balance_sheets
            and not company_financials.cash_flow_statements
        ):
            raise ProviderError(
                FinancialDataErrorCode.MISSING_REQUIRED_DATA,
                f"no usable annual statements could be parsed for '{ticker}'",
            )

        metadata = FinancialDataMetadata(
            provider="indianapi",
            source_identifier=ticker,
            retrieved_at=self._clock().isoformat(),
            currency=currency,
            frequency="annual",
            fiscal_periods=company_financials.fiscal_periods,
        )
        return FinancialDataResult(
            company_financials=company_financials, metadata=metadata, warnings=warnings
        )
