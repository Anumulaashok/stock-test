"""HTTP client for FMP's market-quote endpoints.

Deliberately separate from `app.data.providers.fmp_client.FMPClient`
(which serves the financial-*statement* endpoints) even though both
target the same vendor/account — market quotes are a different domain
(`app/market/`) from financial statements (`app/data/`), and the two
clients must not be conflated per this project's architectural rule.

Endpoints (FMP's stable API, same auth convention as the statement
client — `apikey` query param):

    GET {base_url}/quote?symbol={ticker}
    GET {base_url}/historical-price-eod/full?symbol={ticker}

Field names below are corroborated across FMP's own published docs and
independent third-party references (`price`, `change`, `changePercentage`,
`previousClose`, `timestamp` for quotes; `date`, `open`, `high`, `low`,
`close`, `volume` for historical prices) — this project did not have a
live FMP market-data key available to independently verify them the way
Steps 7/8 verified their providers with a real request; treat this as a
**documented, not live-verified**, integration (see the accompanying
report's Known Limitations).
"""

import asyncio
import logging

import httpx

from app.market.exceptions import MarketProviderError
from app.models.market import MarketDataErrorCode

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


class FMPMarketClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        connect_timeout_seconds: float = 5.0,
        timeout_seconds: float = 10.0,
        max_retries: int = 1,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required for FMPMarketClient")
        if not api_key:
            raise ValueError("api_key is required for FMPMarketClient")

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
                logger.error("Market data provider request timed out at %s", path)
                raise MarketProviderError(
                    MarketDataErrorCode.PROVIDER_UNAVAILABLE, "market data provider request timed out"
                ) from exc
            except httpx.RequestError as exc:
                if attempt < self._max_retries:
                    attempt += 1
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.error("Market data provider request failed at %s: %s", path, exc)
                raise MarketProviderError(
                    MarketDataErrorCode.PROVIDER_UNAVAILABLE, "market data provider request failed"
                ) from exc

            if response.status_code in (401, 403):
                raise MarketProviderError(
                    MarketDataErrorCode.AUTHENTICATION_FAILED,
                    "market data provider rejected the configured API key",
                )
            if response.status_code == 404:
                raise MarketProviderError(
                    MarketDataErrorCode.TICKER_NOT_FOUND,
                    "market data provider returned 404 for this identifier",
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
                raise MarketProviderError(
                    MarketDataErrorCode.RATE_LIMITED,
                    "market data provider rate limit exceeded",
                    retry_after=retry_after,
                )
            if response.status_code in _RETRYABLE_STATUS_CODES:
                if attempt < self._max_retries:
                    attempt += 1
                    await asyncio.sleep(0.5 * attempt)
                    continue
                raise MarketProviderError(
                    MarketDataErrorCode.PROVIDER_UNAVAILABLE,
                    f"market data provider returned status {response.status_code}",
                )
            if response.status_code >= 400:
                raise MarketProviderError(
                    MarketDataErrorCode.INVALID_RESPONSE,
                    f"market data provider returned status {response.status_code}",
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise MarketProviderError(
                    MarketDataErrorCode.INVALID_RESPONSE, "market data provider returned malformed JSON"
                ) from exc

            if not isinstance(data, list):
                raise MarketProviderError(
                    MarketDataErrorCode.SCHEMA_MISMATCH,
                    "market data provider response was not a list of records",
                )

            return data

    async def get_quote(self, ticker: str) -> dict:
        records = await self._get("/quote", {"symbol": ticker})
        if not records:
            raise MarketProviderError(
                MarketDataErrorCode.TICKER_NOT_FOUND, f"no quote was found for '{ticker}'"
            )
        return records[0]

    async def get_historical_prices(self, ticker: str, limit: int) -> list[dict]:
        records = await self._get("/historical-price-eod/full", {"symbol": ticker})
        return records[:limit]
