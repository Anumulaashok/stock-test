"""Deep OHLCV history for the ML pipeline.

`daily_price_history` (see `app.db.models.DailyPriceHistoryRow`) is the
project's persistent price store, but it is only close+volume and, as of
this subsystem's introduction, only 1-249 rows deep per ticker -- nowhere
near the years of history walk-forward validation and historical analogs
need, and missing open/high/low entirely (no ATR, no high/low range, no
gap features from it).

`YFinanceClient.get_history` (already used by `YFinanceMarketProvider` for
live quotes) returns real OHLCV and, live-verified, up to ~5 years / 1,240
trading sessions per NSE ticker with no API key. This module calls it
directly with a long period, deliberately bypassing the
`historical_price_providers` fallback chain (screener/fmp in that chain
return much shallower or close-only data) -- reusing the existing
provider *class*, not duplicating its HTTP logic, while explicitly
requiring the one provider capable of the depth and shape this subsystem
needs.
"""

import logging
from dataclasses import dataclass

import pandas as pd

from app.market.providers.yfinance_client import YFinanceClient
from app.sources.identity import CompanyIdentityResolver, Exchange, to_yfinance_symbol

logger = logging.getLogger(__name__)

_IDENTITY_RESOLVER = CompanyIdentityResolver()

# NIFTY 50 -- the default benchmark for relative-strength/abnormal-return
# features (see app.forecasting.ml.features / app.forecasting.ml.news.event_study).
NIFTY_50_SYMBOL = "^NSEI"

PRICE_COLUMNS = ["open", "high", "low", "close", "volume"]


@dataclass(frozen=True)
class PriceHistoryResult:
    ticker: str
    yfinance_symbol: str
    frame: pd.DataFrame  # DatetimeIndex (date, tz-naive), columns: PRICE_COLUMNS
    warning: str | None = None

    @property
    def is_usable(self) -> bool:
        return not self.frame.empty


def _records_to_frame(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    frame = pd.DataFrame.from_records(records)
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None).dt.normalize()
    frame = frame.rename(columns={c: c for c in PRICE_COLUMNS})
    frame = frame.set_index("date")[PRICE_COLUMNS].astype(float)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    frame = frame.dropna(subset=["close"])
    return frame


class MlPriceHistoryService:
    """Thin wrapper around `YFinanceClient` for the ML pipeline. Every
    failure returns an empty, `is_usable=False` result rather than
    raising -- callers (feature generation, backtesting, the prediction
    API) must all degrade gracefully per spec section 28, never crash a
    stock page because Yahoo Finance is briefly unavailable."""

    def __init__(self, client: YFinanceClient | None = None) -> None:
        self._client = client or YFinanceClient()

    async def get_history(self, ticker: str, *, period: str = "5y") -> PriceHistoryResult:
        identity = _IDENTITY_RESOLVER.resolve_offline(ticker)
        primary_symbol = identity.yfinance_symbol or ticker
        # `resolve_offline` defaults every ticker to NSE (see its
        # docstring): a BSE-only listing (e.g. DANLAW -- see spec section
        # 35's validation ticker) 404s on `.NS` and must be retried on
        # `.BO` rather than reported as having no history at all.
        fallback_symbol = (
            to_yfinance_symbol(ticker, Exchange.BSE) if identity.exchange == Exchange.NSE else None
        )

        frame, warning = await self._fetch(primary_symbol, period)
        if not frame.empty:
            return PriceHistoryResult(ticker=ticker, yfinance_symbol=primary_symbol, frame=frame)

        if fallback_symbol and fallback_symbol != primary_symbol:
            logger.info("ml_price_history_bse_fallback ticker=%s nse_symbol=%s bse_symbol=%s", ticker, primary_symbol, fallback_symbol)
            frame, fallback_warning = await self._fetch(fallback_symbol, period)
            if not frame.empty:
                return PriceHistoryResult(ticker=ticker, yfinance_symbol=fallback_symbol, frame=frame)
            warning = fallback_warning or warning

        return PriceHistoryResult(
            ticker=ticker, yfinance_symbol=primary_symbol, frame=pd.DataFrame(columns=PRICE_COLUMNS),
            warning=warning or "no historical data returned",
        )

    async def _fetch(self, symbol: str, period: str) -> tuple[pd.DataFrame, str | None]:
        try:
            records = await self._client.get_history(symbol, period=period)
        except Exception as exc:  # noqa: BLE001 - provider raises untyped errors
            logger.warning("ml_price_history_fetch_failed symbol=%s error=%s", symbol, exc)
            return pd.DataFrame(columns=PRICE_COLUMNS), f"history fetch failed: {exc}"
        frame = _records_to_frame(records)
        return frame, None if not frame.empty else "no historical data returned"

    async def get_benchmark_history(self, *, period: str = "5y") -> PriceHistoryResult:
        return await self.get_history(NIFTY_50_SYMBOL, period=period)
