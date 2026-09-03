from decimal import Decimal

from app.market.mappers.yfinance import map_historical_prices, map_quote
from app.models.market import PriceFreshness

# fast_info shape below is the actual live field set yfinance's
# Ticker.fast_info returns for an NSE ticker (verified live against
# RELIANCE.NS on 2026-09-03) -- lastPrice/previousClose/marketCap/
# yearHigh/yearLow/currency, no per-quote timestamp.
_FAST_INFO = {
    "currency": "INR",
    "dayHigh": 1316.8,
    "dayLow": 1302.5,
    "lastPrice": 1302.5,
    "lastVolume": 9716604,
    "marketCap": 17626045607087.5,
    "previousClose": 1313.1,
    "yearHigh": 1611.8,
    "yearLow": 1249.8,
}


def test_map_quote_reads_current_and_previous_price():
    quote = map_quote(_FAST_INFO, "RELIANCE.NS")
    assert quote.ticker == "RELIANCE.NS"
    assert quote.current_price == Decimal("1302.5")
    assert quote.previous_close == Decimal("1313.1")
    assert quote.currency == "INR"
    assert quote.source == "yfinance"


def test_map_quote_computes_change_and_change_percent():
    quote = map_quote(_FAST_INFO, "RELIANCE.NS")
    assert quote.change == Decimal("1302.5") - Decimal("1313.1")
    assert quote.change_percent is not None


def test_map_quote_populates_market_cap_and_year_high_low():
    quote = map_quote(_FAST_INFO, "RELIANCE.NS")
    assert quote.market_cap == Decimal("17626045607087.5")
    assert quote.year_high == Decimal("1611.8")
    assert quote.year_low == Decimal("1249.8")


def test_map_quote_never_claims_live_freshness():
    # yfinance is unofficial/unverifiable real-time -- must always be
    # DELAYED (or UNAVAILABLE), matching FMP's mapper policy.
    quote = map_quote(_FAST_INFO, "RELIANCE.NS")
    assert quote.freshness == PriceFreshness.DELAYED


def test_map_quote_marks_unavailable_when_no_price():
    quote = map_quote({"currency": "INR"}, "RELIANCE.NS")
    assert quote.current_price is None
    assert quote.freshness == PriceFreshness.UNAVAILABLE


def test_map_historical_prices_keeps_real_ohlcv():
    records = [
        {"date": "2026-09-01T00:00:00+05:30", "open": 1285.0, "high": 1311.8, "low": 1280.0, "close": 1298.0, "volume": 10_000_000},
        {"date": "2026-09-02T00:00:00+05:30", "open": 1298.0, "high": 1321.9, "low": 1290.0, "close": 1313.1, "volume": 12_000_000},
    ]
    points = map_historical_prices(records)
    assert len(points) == 2
    assert points[0].open == Decimal("1285.0")
    assert points[0].high == Decimal("1311.8")
    assert points[0].low == Decimal("1280.0")
    assert points[0].close == Decimal("1298.0")
    assert points[0].volume == Decimal("10000000")


def test_map_historical_prices_skips_records_without_a_date():
    records = [{"open": 1.0, "close": 2.0}]
    assert map_historical_prices(records) == []
