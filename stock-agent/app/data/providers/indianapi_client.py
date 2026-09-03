"""HTTP client for the IndianAPI stock data service (stock.indianapi.in).

Public docs for this API are thin/unofficial — the request/response
shape below was confirmed with a **real, live request** made during
implementation (not assumed):

    GET {base_url}/stock?name={company_name_or_search_term}
    Header: X-Api-Key: <key>

This API is name-search based (the query param is literally `name`),
not a strict exchange-ticker lookup — `IndianAPIProvider` maps our
canonical `ticker` identifier onto this param; nothing about that leaks
past this module. A successful response is a single JSON *object* (not
a list, unlike FMP) containing many fields, including a `financials`
array of per-period statement entries.

Two behaviors verified live and worth calling out:
- An unmatched company name returns **HTTP 200** with a JSON body of
  `{"error": "Stock not found"}` — not a 404. This client detects that
  shape explicitly and raises `COMPANY_NOT_FOUND`.
- An invalid API key returns HTTP 401 with a **plain-text** body (not
  JSON) — this client never assumes an error body is parseable JSON.

This class only knows HTTP — no financial-statement mapping happens
here (see `app/data/mappers/indianapi.py`).
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


class IndianAPIClient:
    """Talks to the IndianAPI REST API. Retries connection failures,
    timeouts, and 5xx responses a bounded number of times with a short
    fixed backoff; never retries auth failures or not-found responses."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        connect_timeout_seconds: float = 5.0,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required for IndianAPIClient")
        if not api_key:
            raise ValueError("api_key is required for IndianAPIClient")

        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout=timeout_seconds, connect=connect_timeout_seconds)
        self._max_retries = max_retries

    async def get_stock(self, name: str) -> dict:
        data = await self._get_json_object("/stock", {"name": name})
        # HTTP 200 + {"error": "..."} is this provider's not-found
        # signal — verified live against a real unmatched company name.
        if "error" in data:
            raise ProviderError(
                FinancialDataErrorCode.COMPANY_NOT_FOUND,
                f"no data was found for '{name}'",
            )
        return data

    async def get_historical_stat(self, name: str, stats: str) -> dict:
        """`/historical_stats?stock_name={name}&stats={stats}` -- the
        fallback financial-data source (see `app.data.mappers.indianapi_historical`)
        used when `/stock`'s own `financials` field is `null`. `stats` is
        one of `"balancesheet"`, `"cashflow"`, `"ratios"`, `"quarter_results"`.
        Response shape is `{metric_name: {period_label: value}}` -- verified
        live for HUDCO (2026-09-03).
        """
        data = await self._get_json_object(
            "/historical_stats", {"stock_name": name, "stats": stats}
        )
        if "error" in data:
            raise ProviderError(
                FinancialDataErrorCode.COMPANY_NOT_FOUND,
                f"no {stats} data was found for '{name}'",
            )
        return data

    async def get_historical_balance_sheet(self, name: str) -> dict:
        return await self.get_historical_stat(name, "balancesheet")

    async def get_historical_cash_flow(self, name: str) -> dict:
        return await self.get_historical_stat(name, "cashflow")

    async def get_historical_ratios(self, name: str) -> dict:
        return await self.get_historical_stat(name, "ratios")

    async def get_historical_quarter_results(self, name: str) -> dict:
        return await self.get_historical_stat(name, "quarter_results")

    async def get_historical_prices(self, name: str, period: str = "1yr") -> dict:
        """Daily closing-price history from the `/historical_data` endpoint
        (same account/auth as `/stock`) — verified live: returns
        `{"datasets": [{"metric": "Price", "values": [[date, price], ...]}]}`.
        """
        data = await self._get_json_object(
            "/historical_data", {"stock_name": name, "period": period, "filter": "price"}
        )
        if "error" in data:
            raise ProviderError(
                FinancialDataErrorCode.COMPANY_NOT_FOUND,
                f"no historical price data was found for '{name}'",
            )
        return data

    async def _get_json_object(self, path: str, params: dict) -> dict:
        attempt = 0
        while True:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(
                        f"{self._base_url}{path}",
                        params=params,
                        headers={"X-Api-Key": self._api_key},
                    )
            except httpx.TimeoutException as exc:
                if attempt < self._max_retries:
                    attempt += 1
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.error("Financial data provider request timed out for %s", path)
                raise ProviderError(
                    FinancialDataErrorCode.PROVIDER_UNAVAILABLE,
                    "financial data provider request timed out",
                ) from exc
            except httpx.RequestError as exc:
                if attempt < self._max_retries:
                    attempt += 1
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.error("Financial data provider request failed for %s: %s", path, exc)
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
                    f"no data was found for the requested identifier at {path}",
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

            if not isinstance(data, dict):
                raise ProviderError(
                    FinancialDataErrorCode.SCHEMA_MISMATCH,
                    "financial data provider response was not a JSON object",
                )

            return data
