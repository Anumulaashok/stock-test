from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.market.providers.yfinance import YFinanceMarketProvider

_FAST_INFO = {
    "currency": "INR",
    "lastPrice": 1302.5,
    "marketCap": 17626045607087.5,
    "previousClose": 1313.1,
    "yearHigh": 1611.8,
    "yearLow": 1249.8,
}

_HISTORY_RECORDS = [
    {"date": f"2026-08-{day:02d}T00:00:00+05:30", "open": 1280 + day, "high": 1290 + day, "low": 1270 + day, "close": 1285 + day, "volume": 1_000_000}
    for day in range(1, 11)
]


def _provider(client=None) -> YFinanceMarketProvider:
    return YFinanceMarketProvider(client or AsyncMock())


@pytest.mark.asyncio
async def test_get_quote_maps_reliance_fast_info():
    client = AsyncMock()
    client.get_fast_info.return_value = _FAST_INFO
    quote = await _provider(client).get_quote("RELIANCE.NS")
    assert quote.ticker == "RELIANCE.NS"
    assert quote.current_price == Decimal("1302.5")
    assert quote.market_cap == Decimal("17626045607087.5")
    assert quote.year_high == Decimal("1611.8")
    assert quote.year_low == Decimal("1249.8")
    client.get_fast_info.assert_awaited_once_with("RELIANCE.NS")


@pytest.mark.asyncio
async def test_get_recent_prices_maps_and_trims_to_limit():
    client = AsyncMock()
    client.get_history.return_value = _HISTORY_RECORDS
    points = await _provider(client).get_recent_prices("RELIANCE.NS", limit=5)
    assert len(points) == 5
    assert points[0].open is not None
    assert points[0].volume == Decimal("1000000")
    client.get_history.assert_awaited_once_with("RELIANCE.NS", period="1y")


@pytest.mark.asyncio
async def test_get_recent_prices_uses_multi_year_period_for_large_limits():
    client = AsyncMock()
    client.get_history.return_value = _HISTORY_RECORDS
    await _provider(client).get_recent_prices("RELIANCE.NS", limit=1000)
    client.get_history.assert_awaited_once_with("RELIANCE.NS", period="5y")
