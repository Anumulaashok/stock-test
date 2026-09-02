from datetime import datetime, timezone
from decimal import Decimal

from app.market.mappers.indianapi import map_historical_prices, map_quote
from app.models.market import PriceFreshness


def test_map_quote_prefers_nse_over_bse():
    raw = {
        "currentPrice": {"NSE": "1720.50", "BSE": "1715.00"},
        "percentChange": "1.40",
        "stockDetailsReusableData": {"close": "1691.25", "date": "27 Aug 2026", "time": "09:57:40"},
    }
    quote = map_quote(raw, "DANLAW", now=datetime(2026, 8, 27, 10, 0, 0, tzinfo=timezone.utc))
    assert quote.current_price == Decimal("1720.50")
    assert quote.previous_close == Decimal("1691.25")
    assert quote.change == Decimal("29.25")
    assert quote.currency == "INR"
    assert quote.source == "indianapi"


def test_map_quote_falls_back_to_bse_when_nse_is_null_or_zero():
    raw = {"currentPrice": {"NSE": None, "BSE": "1715.00"}}
    quote = map_quote(raw, "DANLAW")
    assert quote.current_price == Decimal("1715.00")

    raw_zero = {"currentPrice": {"NSE": "0.00", "BSE": "1715.00"}}
    quote_zero = map_quote(raw_zero, "DANLAW")
    assert quote_zero.current_price == Decimal("1715.00")


def test_map_quote_missing_current_price_is_unavailable_not_zero():
    quote = map_quote({}, "DANLAW")
    assert quote.current_price is None
    assert quote.freshness == PriceFreshness.UNAVAILABLE


def test_map_quote_never_fabricates_missing_fields():
    quote = map_quote({"currentPrice": {"NSE": "100"}}, "DANLAW")
    assert quote.previous_close is None
    assert quote.change is None
    assert quote.change_percent is None


def test_map_quote_old_market_timestamp_is_stale():
    raw = {
        "currentPrice": {"NSE": "100"},
        "stockDetailsReusableData": {"date": "20 Aug 2026", "time": "09:00:00"},
    }
    quote = map_quote(raw, "DANLAW", now=datetime(2026, 8, 27, 10, 0, 0, tzinfo=timezone.utc))
    assert quote.freshness == PriceFreshness.STALE


def test_map_historical_prices_extracts_the_price_dataset():
    raw = {
        "datasets": [
            {"metric": "Volume", "values": [["2026-08-20", "1000"]]},
            {"metric": "Price", "values": [["2026-08-20", "100.5"], ["2026-08-21", "101.0"]]},
        ]
    }
    points = map_historical_prices(raw)
    assert len(points) == 2
    assert points[0].timestamp == "2026-08-20"
    assert points[0].close == Decimal("100.5")
    assert points[0].open == points[0].high == points[0].low == points[0].close


def test_map_historical_prices_missing_dataset_is_empty():
    assert map_historical_prices({}) == []
    assert map_historical_prices({"datasets": []}) == []


def test_map_historical_prices_skips_malformed_entries():
    raw = {"datasets": [{"metric": "Price", "values": [["2026-08-20"], ["2026-08-21", "101.0"], [None, "5"]]}]}
    points = map_historical_prices(raw)
    assert len(points) == 1
    assert points[0].timestamp == "2026-08-21"
