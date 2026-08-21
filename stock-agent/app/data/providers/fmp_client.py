"""HTTP client for the Financial Modeling Prep (FMP) API.

Chosen provider — see the Step 7 report for the full rationale. In
summary: FMP's REST API (site.financialmodelingprep.com/developer/docs)
authenticates via an `apikey` query parameter, returns JSON, and its
free tier (250 requests/day, verified via FMP's own pricing page and
third-party reviews as of 2026) includes the income-statement,
balance-sheet-statement, and cash-flow-statement endpoints for both
annual and quarterly periods — exactly what this project needs. No
official Python SDK dependency was added; this is a plain `httpx` client
matching the project's existing HTTP-client style (see `LocalLLMProvider`).

This class only knows HTTP — no financial-statement mapping happens
here (see `app/data/mappers/fmp.py`).
"""

import asyncio
import logging

import httpx

from app.data.exceptions import ProviderError
from app.data.models import FinancialDataErrorCode

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
_MAX_RATE_LIMIT_WAIT_SECONDS = 10.0


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class FMPClient:
    """Talks to the FMP REST API. Retries connection failures, timeouts,
    and 5xx responses a bounded number of times with a short fixed
    backoff; never retries auth failures, 404s, or schema problems."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        connect_timeout_seconds: float = 5.0,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required for FMPClient")
        if not api_key:
            raise ValueError("api_key is required for FMPClient")

        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout=timeout_seconds, connect=connect_timeout_seconds)
        self._max_retries = max_retries

    async def _get(self, path: str, params: dict) -> list[dict]:
        query = {**params, "apikey": self._api_key}
        attempt = 0

        while True:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(f"{self._base_url}{path}", params=query)
            except httpx.TimeoutException as exc:
                if attempt < self._max_retries:
                    attempt += 1
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.error("Financial data provider request timed out at %s", path)
                raise ProviderError(
                    FinancialDataErrorCode.PROVIDER_UNAVAILABLE,
                    "financial data provider request timed out",
                ) from exc
            except httpx.RequestError as exc:
                if attempt < self._max_retries:
                    attempt += 1
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.error("Financial data provider request failed at %s: %s", path, exc)
                raise ProviderError(
                    FinancialDataErrorCode.PROVIDER_UNAVAILABLE,
                    "financial data provider request failed",
                ) from exc

            if response.status_code in (401, 403):
                raise ProviderError(
                    FinancialDataErrorCode.AUTHENTICATION_FAILED,
                    "financial data provider rejected the configured API key",
                )
            if response.status_code == 404:
                raise ProviderError(
                    FinancialDataErrorCode.COMPANY_NOT_FOUND,
                    "financial data provider returned 404 for this identifier",
                )
            if response.status_code == 429:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                if (
                    attempt < self._max_retries
                    and retry_after is not None
                    and retry_after <= _MAX_RATE_LIMIT_WAIT_SECONDS
                ):
                    attempt += 1
                    await asyncio.sleep(retry_after)
                    continue
                raise ProviderError(
                    FinancialDataErrorCode.RATE_LIMITED,
                    "financial data provider rate limit exceeded",
                    retry_after=retry_after,
                )
            if response.status_code in _RETRYABLE_STATUS_CODES:
                if attempt < self._max_retries:
                    attempt += 1
                    await asyncio.sleep(0.5 * attempt)
                    continue
                raise ProviderError(
                    FinancialDataErrorCode.PROVIDER_UNAVAILABLE,
                    f"financial data provider returned status {response.status_code}",
                )
            if response.status_code >= 400:
                raise ProviderError(
                    FinancialDataErrorCode.INVALID_RESPONSE,
                    f"financial data provider returned status {response.status_code}",
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise ProviderError(
                    FinancialDataErrorCode.INVALID_RESPONSE,
                    "financial data provider returned malformed JSON",
                ) from exc

            if not isinstance(data, list):
                raise ProviderError(
                    FinancialDataErrorCode.SCHEMA_MISMATCH,
                    "financial data provider response was not a list of statement records",
                )

            return data

    async def get_income_statements(self, ticker: str, limit: int) -> list[dict]:
        return await self._get(
            "/income-statement", {"symbol": ticker, "period": "annual", "limit": limit}
        )

    async def get_balance_sheets(self, ticker: str, limit: int) -> list[dict]:
        return await self._get(
            "/balance-sheet-statement", {"symbol": ticker, "period": "annual", "limit": limit}
        )

    async def get_cash_flow_statements(self, ticker: str, limit: int) -> list[dict]:
        return await self._get(
            "/cash-flow-statement", {"symbol": ticker, "period": "annual", "limit": limit}
        )
