from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.market.mappers.fmp import map_historical_prices, map_quote
from app.models.market import PriceFreshness


def test_map_quote_maps_known_fields():
    now = datetime(2026, 8, 21, tzinfo=timezone.utc)
    raw = {
        "price": 180.5,
        "previousClose": 178.0,
        "change": 2.5,
        "changePercentage": 1.4,
        "currency": "USD",
        "timestamp": int((now - timedelta(hours=1)).timestamp()),
    }
    quote = map_quote(raw, "AAPL", now=now)
    assert quote.ticker == "AAPL"
    assert quote.current_price == Decimal("180.5")
    assert quote.previous_close == Decimal("178.0")
    assert quote.change == Decimal("2.5")
    assert quote.currency == "USD"
    assert quote.source == "fmp"


def test_map_quote_missing_price_is_unavailable_not_zero():
    quote = map_quote({}, "AAPL")
    assert quote.current_price is None
    assert quote.freshness == PriceFreshness.UNAVAILABLE


def test_map_quote_without_timestamp_is_delayed_not_live():
    quote = map_quote({"price": 100}, "AAPL")
    assert quote.current_price == Decimal("100")
    assert quote.freshness == PriceFreshness.DELAYED


def test_map_quote_old_timestamp_is_stale():
    now = datetime(2026, 8, 21, tzinfo=timezone.utc)
    old_timestamp = int((now - timedelta(days=3)).timestamp())
    quote = map_quote({"price": 100, "timestamp": old_timestamp}, "AAPL", now=now)
    assert quote.freshness == PriceFreshness.STALE


def test_map_quote_never_fabricates_missing_fields():
    quote = map_quote({"price": 100}, "AAPL")
    assert quote.previous_close is None
    assert quote.change is None
    assert quote.change_percent is None
    assert quote.currency is None


def test_map_historical_prices_maps_ohlcv():
    raw = [{"date": "2026-08-20", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "adjClose": 1.4, "volume": 1000}]
    points = map_historical_prices(raw)
    assert len(points) == 1
    point = points[0]
    assert point.timestamp == "2026-08-20"
    assert point.open == Decimal("1")
    assert point.close == Decimal("1.5")
    assert point.adjusted_close == Decimal("1.4")
    assert point.volume == Decimal("1000")


def test_map_historical_prices_skips_records_without_a_date():
    raw = [{"close": 1.5}, {"date": "2026-08-20", "close": 1.5}]
    points = map_historical_prices(raw)
    assert len(points) == 1
    assert points[0].timestamp == "2026-08-20"
