from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from app.forecasting.ml.news.event_study import (
    MIN_EVENT_STUDY_SAMPLE_SIZE,
    aggregate_event_statistics,
    compute_reaction,
)
from app.forecasting.ml.news.models import EventReaction, EventType, MarketTiming, NewsEvent, Sentiment

IST = ZoneInfo("Asia/Kolkata")


def _close_series(n=60, start=100.0) -> pd.Series:
    dates = pd.bdate_range("2026-01-01", periods=n)
    # deterministic +1% per day so reactions are easy to hand-verify
    values = start * (1.01 ** np.arange(n))
    return pd.Series(values, index=dates)


def _event(published_local: datetime, event_type=EventType.ORDER_WIN) -> NewsEvent:
    return NewsEvent(
        ticker="TEST", published_at=published_local.astimezone(timezone.utc),
        headline="Test wins order", event_type=event_type, sentiment=Sentiment.POSITIVE,
        sentiment_score=0.5, importance_score=0.6, market_timing=MarketTiming.MARKET_HOURS,
    )


def test_reaction_uses_price_the_session_before_as_base_not_event_day():
    close = _close_series()
    event = _event(datetime(2026, 1, 6, 10, 0, tzinfo=IST))  # Tuesday, market hours -> same-day reaction
    reaction = compute_reaction(event, stock_close=close)
    assert reaction is not None
    reaction_idx = close.index.get_loc(pd.Timestamp(reaction.reaction_session_date))
    base_price = close.iloc[reaction_idx - 1]
    expected_same_day = close.iloc[reaction_idx] / base_price - 1
    assert reaction.return_same_day == pytest.approx(expected_same_day)


def test_post_market_event_anchors_reaction_on_next_session():
    close = _close_series()
    event = _event(datetime(2026, 1, 6, 17, 0, tzinfo=IST))  # Tuesday post-market
    reaction = compute_reaction(event, stock_close=close)
    assert reaction is not None
    assert pd.Timestamp(reaction.reaction_session_date) == pd.Timestamp("2026-01-07")


def test_event_before_available_history_returns_none_not_fabricated():
    close = _close_series(start=100.0)
    close = close.iloc[5:]  # history starts later
    event = _event(datetime(2025, 12, 1, 10, 0, tzinfo=IST))
    reaction = compute_reaction(event, stock_close=close)
    assert reaction is None


def test_abnormal_return_isolates_stock_specific_move():
    close = _close_series()  # +1%/day
    benchmark = pd.Series(100.0 * (1.002 ** np.arange(len(close))), index=close.index)  # +0.2%/day
    event = _event(datetime(2026, 1, 6, 10, 0, tzinfo=IST))
    reaction = compute_reaction(event, stock_close=close, benchmark_close=benchmark)
    assert reaction is not None
    assert reaction.abnormal_return_5d is not None
    # stock outran the benchmark, so abnormal return should be positive and smaller than the raw return
    assert 0 < reaction.abnormal_return_5d < reaction.return_5d


def _reaction(ticker="TEST", **overrides) -> EventReaction:
    base = dict(
        event_id="x", ticker=ticker, reaction_session_date="2026-01-06",
        return_same_day=0.01, return_1d=0.02, return_3d=0.03, return_5d=0.04, return_14d=0.05, return_30d=0.06,
    )
    base.update(overrides)
    return EventReaction(**base)


def test_aggregate_below_minimum_sample_is_not_reliable():
    stats = aggregate_event_statistics([_reaction() for _ in range(MIN_EVENT_STUDY_SAMPLE_SIZE - 1)])
    assert not stats.is_reliable


def test_aggregate_at_minimum_sample_is_reliable_and_medians_correct():
    reactions = [_reaction(return_5d=0.10) for _ in range(MIN_EVENT_STUDY_SAMPLE_SIZE)]
    stats = aggregate_event_statistics(reactions)
    assert stats.is_reliable
    assert stats.median_return_by_horizon["return_5d"] == pytest.approx(0.10)
    assert stats.positive_rate_by_horizon["return_5d"] == 1.0
