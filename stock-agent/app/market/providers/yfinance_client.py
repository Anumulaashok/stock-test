"""Blocking-call wrapper around the `yfinance` library (unofficial Yahoo
Finance scraper, no API key). yfinance's own client is synchronous, so
every call here runs via `asyncio.to_thread` to avoid blocking the event
loop -- the same constraint every other provider's `httpx.AsyncClient`
satisfies natively.

Returns plain dicts/lists (never yfinance's own objects), mirroring
`FMPMarketClient`/`IndianAPIClient` so `app.market.mappers.yfinance` stays
a pure, yfinance-independent transform.

Field provenance (live-verified against RELIANCE.NS, 2026-09-03):
- `Ticker.fast_info` -- NOT `Ticker.info`, which returns `None` for
  `marketCap` on Indian tickers -- gives `lastPrice`, `previousClose`,
  `marketCap`, `yearHigh`, `yearLow`, `currency`, `lastVolume`.
- `Ticker.history(period=...)` gives a DataFrame with
  `Open`/`High`/`Low`/`Close`/`Volume` columns and a `DatetimeIndex`.
"""

import asyncio
import logging

import yfinance as yf

from app.market.exceptions import MarketProviderError
from app.models.market import MarketDataErrorCode

logger = logging.getLogger(__name__)


class YFinanceClient:
    async def get_fast_info(self, ticker: str) -> dict:
        return await asyncio.to_thread(self._fetch_fast_info, ticker)

    def _fetch_fast_info(self, ticker: str) -> dict:
        try:
            fast_info = yf.Ticker(ticker).fast_info
            data = dict(fast_info)
        except Exception as exc:  # noqa: BLE001 - yfinance raises various untyped errors
            logger.error("yfinance fast_info request failed for %s: %s", ticker, exc)
            raise MarketProviderError(
                MarketDataErrorCode.PROVIDER_UNAVAILABLE, "yfinance fast_info request failed"
            ) from exc

        if not data or data.get("lastPrice") is None:
            raise MarketProviderError(
                MarketDataErrorCode.TICKER_NOT_FOUND, f"no quote was found for '{ticker}'"
            )
        return data

    async def get_history(self, ticker: str, period: str) -> list[dict]:
        return await asyncio.to_thread(self._fetch_history, ticker, period)

    def _fetch_history(self, ticker: str, period: str) -> list[dict]:
        try:
            df = yf.Ticker(ticker).history(period=period)
        except Exception as exc:  # noqa: BLE001 - yfinance raises various untyped errors
            logger.error("yfinance history request failed for %s: %s", ticker, exc)
            raise MarketProviderError(
                MarketDataErrorCode.PROVIDER_UNAVAILABLE, "yfinance history request failed"
            ) from exc

        records: list[dict] = []
        for index, row in df.iterrows():
            records.append(
                {
                    "date": index.isoformat(),
                    "open": row.get("Open"),
                    "high": row.get("High"),
                    "low": row.get("Low"),
                    "close": row.get("Close"),
                    "volume": row.get("Volume"),
                }
            )
        return records
