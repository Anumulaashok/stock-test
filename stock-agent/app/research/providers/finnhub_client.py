"""HTTP client for the Finnhub company-news API.

Chosen provider (see Step 8 report): Finnhub's `/company-news` endpoint
(finnhub.io/docs/api/company-news) — official documented REST API,
`token` query-param (or `X-Finnhub-Token` header) authentication, JSON
responses, a free tier (60 requests/minute, no credit card required)
that includes company news scoped by ticker and date range. This class
only knows HTTP — no article mapping happens here (see
`app/research/mappers/finnhub.py`).
"""

import asyncio
import logging

import httpx

from app.models.research import ResearchErrorCode
from app.research.exceptions import ResearchProviderError

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


class FinnhubClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        connect_timeout_seconds: float = 5.0,
        timeout_seconds: float = 10.0,
        max_retries: int = 1,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required for FinnhubClient")
        if not api_key:
            raise ValueError("api_key is required for FinnhubClient")

        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout=timeout_seconds, connect=connect_timeout_seconds)
        self._max_retries = max_retries

    async def get_company_news(self, ticker: str, from_date: str, to_date: str) -> list[dict]:
        query = {"symbol": ticker, "from": from_date, "to": to_date, "token": self._api_key}
        attempt = 0

        while True:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(f"{self._base_url}/company-news", params=query)
            except httpx.TimeoutException as exc:
                if attempt < self._max_retries:
                    attempt += 1
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.error("Research provider request timed out for %s", ticker)
                raise ResearchProviderError(
                    ResearchErrorCode.PROVIDER_UNAVAILABLE, "research provider request timed out"
                ) from exc
            except httpx.RequestError as exc:
                if attempt < self._max_retries:
                    attempt += 1
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.error("Research provider request failed for %s: %s", ticker, exc)
                raise ResearchProviderError(
                    ResearchErrorCode.PROVIDER_UNAVAILABLE, "research provider request failed"
                ) from exc

            if response.status_code in (401, 403):
                raise ResearchProviderError(
                    ResearchErrorCode.AUTHENTICATION_FAILED,
                    "research provider rejected the configured API key",
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
                raise ResearchProviderError(
                    ResearchErrorCode.RATE_LIMITED,
                    "research provider rate limit exceeded",
                    retry_after=retry_after,
                )
            if response.status_code in _RETRYABLE_STATUS_CODES:
                if attempt < self._max_retries:
                    attempt += 1
                    await asyncio.sleep(0.5 * attempt)
                    continue
                raise ResearchProviderError(
                    ResearchErrorCode.PROVIDER_UNAVAILABLE,
                    f"research provider returned status {response.status_code}",
                )
            if response.status_code >= 400:
                raise ResearchProviderError(
                    ResearchErrorCode.INVALID_RESPONSE,
                    f"research provider returned status {response.status_code}",
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise ResearchProviderError(
                    ResearchErrorCode.INVALID_RESPONSE, "research provider returned malformed JSON"
                ) from exc

            if not isinstance(data, list):
                raise ResearchProviderError(
                    ResearchErrorCode.INVALID_RESPONSE,
                    "research provider response was not a list of articles",
                )

            return data
