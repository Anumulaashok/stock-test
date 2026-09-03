from decimal import Decimal

import httpx
import pytest
import respx

from app.market.exceptions import MarketProviderError
from app.market.providers.fmp import FMPMarketProvider
from app.market.providers.fmp_client import FMPMarketClient
from app.models.market import MarketDataErrorCode, PriceFreshness

BASE_URL = "http://test-fmp:9999"


def _provider(max_retries: int = 0) -> FMPMarketProvider:
    client = FMPMarketClient(base_url=BASE_URL, api_key="test-key", max_retries=max_retries)
    return FMPMarketProvider(client)


# Response shapes below are the actual live fields returned by FMP's
# stable /quote and /historical-price-eod/full endpoints for a US
# ticker (verified live against this project's own trial key on
# 2026-09-03) -- not reconstructed from docs alone.
@pytest.mark.asyncio
@respx.mock
async def test_get_quote_maps_current_price():
    respx.get(f"{BASE_URL}/quote").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "symbol": "AAPL",
                    "price": 324.96,
                    "changePercentage": -0.05228678,
                    "change": -0.17,
                    "previousClose": 325.13,
                    "timestamp": 1788379201,
                }
            ],
        )
    )
    quote = await _provider().get_quote("AAPL")
    assert quote.ticker == "AAPL"
    assert quote.current_price == Decimal("324.96")
    assert quote.previous_close == Decimal("325.13")
    assert quote.source == "fmp"
    assert quote.freshness == PriceFreshness.DELAYED


@pytest.mark.asyncio
@respx.mock
async def test_get_quote_translates_ticker_not_found():
    respx.get(f"{BASE_URL}/quote").mock(return_value=httpx.Response(200, json=[]))
    with pytest.raises(MarketProviderError) as exc_info:
        await _provider().get_quote("NOPE")
    assert exc_info.value.code == MarketDataErrorCode.TICKER_NOT_FOUND


@pytest.mark.asyncio
@respx.mock
async def test_get_quote_translates_plan_restricted_symbol():
    # FMP's trial plan returns 402 ("Premium Query Parameter") for
    # symbols outside the account's subscription (e.g. non-US tickers).
    respx.get(f"{BASE_URL}/quote").mock(return_value=httpx.Response(402, text="Premium Query Parameter"))
    with pytest.raises(MarketProviderError) as exc_info:
        await _provider().get_quote("RELIANCE.NS")
    assert exc_info.value.code == MarketDataErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
@respx.mock
async def test_get_recent_prices_maps_and_trims_to_limit():
    records = [
        {"symbol": "AAPL", "date": f"2026-08-{day:02d}", "open": 100 + day, "high": 101 + day, "low": 99 + day, "close": 100.5 + day, "volume": 1000}
        for day in range(1, 21)
    ]
    respx.get(f"{BASE_URL}/historical-price-eod/full").mock(return_value=httpx.Response(200, json=records))
    points = await _provider().get_recent_prices("AAPL", limit=5)
    assert len(points) == 5
    assert points[0].timestamp == "2026-08-01"


@pytest.mark.asyncio
@respx.mock
async def test_get_recent_prices_translates_provider_error():
    respx.get(f"{BASE_URL}/historical-price-eod/full").mock(return_value=httpx.Response(401, json={}))
    with pytest.raises(MarketProviderError) as exc_info:
        await _provider().get_recent_prices("AAPL", limit=30)
    assert exc_info.value.code == MarketDataErrorCode.AUTHENTICATION_FAILED
