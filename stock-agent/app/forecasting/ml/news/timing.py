"""Market-timing classification for a news item's publication timestamp
(spec section 8/10) -- NSE/BSE trading hours, IST.

Assumption (documented per spec section 15, since this codebase has no
NSE holiday calendar anywhere -- `app.forecasting.calculations` notes
the same limitation for `project_trading_date`): a weekday that isn't a
weekend is assumed to be a trading day. A genuine NSE holiday
publication is misclassified as PRE_MARKET/MARKET_HOURS/POST_MARKET
rather than HOLIDAY until a holiday calendar is integrated -- callers
that need the *next actual trading session* should resolve it against
the real observed price series (`app.forecasting.ml.data`), not this
classifier's calendar-day guess, exactly as `next_trading_session` does.
"""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from app.forecasting.ml.news.models import MarketTiming

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def classify_market_timing(published_at: datetime) -> MarketTiming:
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    local = published_at.astimezone(IST)

    if local.weekday() >= 5:  # Saturday=5, Sunday=6
        return MarketTiming.WEEKEND

    local_time = local.time()
    if local_time < MARKET_OPEN:
        return MarketTiming.PRE_MARKET
    if local_time <= MARKET_CLOSE:
        return MarketTiming.MARKET_HOURS
    return MarketTiming.POST_MARKET


def next_trading_session(published_at: datetime, trading_dates: pd.DatetimeIndex) -> pd.Timestamp | None:
    """The first real observed trading session an event could move the
    price in. A PRE_MARKET or MARKET_HOURS event reacts the same
    session; POST_MARKET, WEEKEND, or HOLIDAY reacts the *next* session
    (spec section 10: "POST_MARKET event -> next trading session becomes
    event reaction day"). Uses the actual observed `trading_dates` index
    (see `app.forecasting.ml.data`) rather than a calendar-day guess, so
    unlisted NSE holidays are handled correctly for free."""
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    local_date = pd.Timestamp(published_at.astimezone(IST).date())
    timing = classify_market_timing(published_at)

    if trading_dates.empty:
        return None

    if timing in (MarketTiming.PRE_MARKET, MarketTiming.MARKET_HOURS):
        candidates = trading_dates[trading_dates >= local_date]
    else:
        candidates = trading_dates[trading_dates > local_date]

    return candidates.min() if len(candidates) else None
