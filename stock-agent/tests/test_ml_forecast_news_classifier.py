from datetime import datetime, timedelta, timezone

from app.forecasting.ml.news.classifier import KeywordEventClassifier
from app.forecasting.ml.news.models import EventType, NewsEvent, Sentiment, MarketTiming
from app.forecasting.ml.news.novelty import compute_novelty_score, estimate_surprise


def test_order_win_headline_classified_correctly():
    result = KeywordEventClassifier().classify("Company X wins order worth Rs 500 crore from Railways")
    assert result.event_type == EventType.ORDER_WIN
    assert result.sentiment == Sentiment.POSITIVE


def test_earnings_miss_headline_is_negative():
    result = KeywordEventClassifier().classify("Company X misses estimates, profit falls 20%")
    assert result.event_type == EventType.EARNINGS_MISS
    assert result.sentiment == Sentiment.NEGATIVE


def test_dividend_keyword_matches_as_a_tuple_not_character_by_character():
    """Regression test: EventType.DIVIDEND's keyword tuple must contain
    the word "dividend", not be an unwrapped string iterated character
    by character."""
    result = KeywordEventClassifier().classify("Board declares special dividend of Rs 5 per share")
    assert result.event_type == EventType.DIVIDEND


def test_unrecognized_headline_is_other_with_low_importance():
    result = KeywordEventClassifier().classify("Company X holds annual general meeting")
    assert result.event_type == EventType.OTHER
    assert result.importance_score < 0.5


def _event(hours_ago: float, headline: str) -> NewsEvent:
    return NewsEvent(
        ticker="TEST", published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        headline=headline, event_type=EventType.ORDER_WIN, sentiment=Sentiment.POSITIVE,
        market_timing=MarketTiming.MARKET_HOURS,
    )


def test_first_report_has_full_novelty():
    current = _event(0, "Company X wins large order from Indian Railways")
    assert compute_novelty_score(current, []) == 1.0


def test_near_duplicate_recent_headline_reduces_novelty():
    prior = _event(2, "Company X wins large order from Indian Railways")
    current = _event(0, "Company X wins large order from Indian Railways")
    novelty = compute_novelty_score(current, [prior])
    assert novelty < 0.5


def test_stale_similar_headline_outside_window_does_not_reduce_novelty():
    prior = _event(72, "Company X wins large order from Indian Railways")  # outside 48h window
    current = _event(0, "Company X wins large order from Indian Railways")
    assert compute_novelty_score(current, [prior]) == 1.0


def test_surprise_none_without_expected_value():
    assert estimate_surprise(expected=None, actual=100.0) is None


def test_surprise_computed_when_both_values_known():
    assert estimate_surprise(expected=100.0, actual=110.0) == 0.1
