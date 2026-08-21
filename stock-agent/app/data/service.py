"""Data-ingestion orchestration.

`FinancialDataService` validates the identifier, delegates to a
`FinancialDataProvider`, and converts any `ProviderError` into a
structured `FinancialDataFetchResult` — callers never need to catch an
exception for an expected failure (not found, provider down, auth
failure, ...). Never calculates a financial ratio, valuation, or score,
and never calls the LLM.
"""

import logging

from app.data.base import FinancialDataProvider
from app.data.exceptions import ProviderError
from app.data.models import (
    CompanyIdentifier,
    FinancialDataError,
    FinancialDataErrorCode,
    FinancialDataFetchResult,
)

logger = logging.getLogger(__name__)


class FinancialDataService:
    def __init__(self, provider: FinancialDataProvider) -> None:
        self._provider = provider

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataFetchResult:
        ticker = (identifier.ticker or "").strip().upper()
        if not ticker:
            return FinancialDataFetchResult(
                status="error",
                error=FinancialDataError(
                    code=FinancialDataErrorCode.MISSING_REQUIRED_DATA,
                    message="a ticker is required",
                ),
            )

        try:
            result = await self._provider.get_company_financials(CompanyIdentifier(ticker=ticker))
        except ProviderError as exc:
            logger.warning(
                "Financial data provider error for %s: %s [%s]", ticker, exc.message, exc.code
            )
            return FinancialDataFetchResult(
                status="error", error=FinancialDataError(code=exc.code, message=exc.message)
            )

        return FinancialDataFetchResult(status="success", data=result)
