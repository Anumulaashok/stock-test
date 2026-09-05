from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.forecasting.ml.news.models import MarketTiming
from app.forecasting.ml.news.timing import classify_market_timing, next_trading_session

IST = ZoneInfo("Asia/Kolkata")


def _ist_naive_as_utc(year, month, day, hour, minute) -> datetime:
    """Build a UTC datetime whose IST wall-clock time is (hour, minute)."""
    local = datetime(year, month, day, hour, minute, tzinfo=IST)
    return local.astimezone(timezone.utc)


@pytest.mark.parametrize(
    "hour,minute,expected",
    [
        (8, 0, MarketTiming.PRE_MARKET),
        (9, 0, MarketTiming.PRE_MARKET),
        (9, 15, MarketTiming.MARKET_HOURS),
        (12, 0, MarketTiming.MARKET_HOURS),
        (15, 30, MarketTiming.MARKET_HOURS),
        (15, 45, MarketTiming.POST_MARKET),
        (20, 0, MarketTiming.POST_MARKET),
    ],
)
def test_weekday_timing_buckets(hour, minute, expected):
    # 2026-09-01 is a Tuesday
    dt = _ist_naive_as_utc(2026, 9, 1, hour, minute)
    assert classify_market_timing(dt) == expected


def test_weekend_is_weekend_regardless_of_time():
    # 2026-09-05 is a Saturday
    dt = _ist_naive_as_utc(2026, 9, 5, 11, 0)
    assert classify_market_timing(dt) == MarketTiming.WEEKEND


def test_naive_datetime_is_treated_as_utc_not_crashing():
    dt = datetime(2026, 9, 1, 10, 0)  # no tzinfo
    result = classify_market_timing(dt)
    assert result in MarketTiming


def _trading_dates() -> pd.DatetimeIndex:
    # Tue 2026-09-01, Wed 2026-09-02, Thu 2026-09-03, Fri 2026-09-04, Mon 2026-09-07
    return pd.DatetimeIndex(["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-07"])


def test_pre_market_event_reacts_same_session():
    dt = _ist_naive_as_utc(2026, 9, 2, 8, 0)  # Wed pre-market
    session = next_trading_session(dt, _trading_dates())
    assert session == pd.Timestamp("2026-09-02")


def test_post_market_event_reacts_next_session_not_same_day():
    """Spec section 10: a POST_MARKET event's reaction day is the NEXT
    trading session, never the event's own calendar date."""
    dt = _ist_naive_as_utc(2026, 9, 2, 16, 0)  # Wed post-market
    session = next_trading_session(dt, _trading_dates())
    assert session == pd.Timestamp("2026-09-03")


def test_weekend_event_reacts_on_next_monday_session_not_calendar_days():
    dt = _ist_naive_as_utc(2026, 9, 5, 10, 0)  # Saturday
    session = next_trading_session(dt, _trading_dates())
    assert session == pd.Timestamp("2026-09-07")  # Monday, correctly skipping the weekend


def test_friday_post_market_skips_to_next_available_session_correctly():
    dt = _ist_naive_as_utc(2026, 9, 4, 18, 0)  # Friday post-market
    session = next_trading_session(dt, _trading_dates())
    assert session == pd.Timestamp("2026-09-07")
