"""FMPProvider: implements `FinancialDataProvider` for Financial Modeling Prep.

Combines `FMPClient` (HTTP) and `app.data.mappers.fmp` (schema mapping)
so FMP's field names (`netIncome`, `cashAndCashEquivalents`, ...) never
leak past this module — everything downstream only sees `CompanyFinancials`.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from app.data.base import FinancialDataProvider
from app.data.exceptions import ProviderError
from app.data.mappers.fmp import build_company_financials
from app.data.models import (
    CompanyIdentifier,
    FinancialDataErrorCode,
    FinancialDataMetadata,
    FinancialDataResult,
)
from app.data.providers.fmp_client import FMPClient

logger = logging.getLogger(__name__)


class FMPProvider(FinancialDataProvider):
    def __init__(
        self,
        client: FMPClient,
        annual_periods_limit: int = 5,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._annual_periods_limit = annual_periods_limit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataResult:
        ticker = identifier.ticker

        income_raw = await self._client.get_income_statements(ticker, self._annual_periods_limit)
        balance_raw = await self._client.get_balance_sheets(ticker, self._annual_periods_limit)
        cash_flow_raw = await self._client.get_cash_flow_statements(
            ticker, self._annual_periods_limit
        )

        # FMP returns HTTP 200 with an empty list for an unknown/invalid
        # ticker rather than a 404 — treat that the same as not-found.
        if not income_raw and not balance_raw and not cash_flow_raw:
            raise ProviderError(
                FinancialDataErrorCode.COMPANY_NOT_FOUND,
                f"no financial statements were found for '{ticker}'",
            )

        # FMP's statement endpoints don't return a display name, only the
        # symbol — the ticker is used as the company name until a future
        # step enriches this via a company-profile lookup.
        company_name = ticker

        company_financials, currency, warnings = build_company_financials(
            company_name=company_name,
            ticker=ticker,
            income_raw=income_raw,
            balance_raw=balance_raw,
            cash_flow_raw=cash_flow_raw,
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
            provider="financial_modeling_prep",
            source_identifier=ticker,
            retrieved_at=self._clock().isoformat(),
            currency=currency,
            frequency="annual",
            fiscal_periods=company_financials.fiscal_periods,
        )
        return FinancialDataResult(
            company_financials=company_financials, metadata=metadata, warnings=warnings
        )
