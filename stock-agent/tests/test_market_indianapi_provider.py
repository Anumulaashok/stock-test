import httpx
import pytest
import respx

from app.data.providers.indianapi_client import IndianAPIClient
from app.market.exceptions import MarketProviderError
from app.market.providers.indianapi import IndianAPIMarketProvider
from app.models.market import MarketDataErrorCode

BASE_URL = "http://test-indianapi:9999"


def _provider() -> IndianAPIMarketProvider:
    client = IndianAPIClient(base_url=BASE_URL, api_key="test-key", max_retries=0)
    return IndianAPIMarketProvider(client)


@pytest.mark.asyncio
@respx.mock
async def test_get_quote_maps_current_price():
    respx.get(f"{BASE_URL}/stock").mock(
        return_value=httpx.Response(200, json={"currentPrice": {"NSE": "1720.50", "BSE": "1715.00"}})
    )
    quote = await _provider().get_quote("DANLAW")
    assert quote.ticker == "DANLAW"
    assert quote.current_price == 1720.50
    assert quote.currency == "INR"
    assert quote.source == "indianapi"


@pytest.mark.asyncio
@respx.mock
async def test_get_quote_translates_provider_error():
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(200, json={"error": "Stock not found"}))
    with pytest.raises(MarketProviderError) as exc_info:
        await _provider().get_quote("NOPE")
    assert exc_info.value.code == MarketDataErrorCode.TICKER_NOT_FOUND


@pytest.mark.asyncio
@respx.mock
async def test_get_recent_prices_maps_and_trims_to_limit():
    values = [[f"2026-01-{day:02d}", str(100 + day)] for day in range(1, 21)]
    respx.get(f"{BASE_URL}/historical_data").mock(
        return_value=httpx.Response(200, json={"datasets": [{"metric": "Price", "values": values}]})
    )
    points = await _provider().get_recent_prices("DANLAW", limit=5)
    assert len(points) == 5
    assert points[-1].timestamp == "2026-01-20"


@pytest.mark.asyncio
@respx.mock
async def test_get_recent_prices_requests_longer_period_for_large_limits():
    route = respx.get(f"{BASE_URL}/historical_data").mock(
        return_value=httpx.Response(200, json={"datasets": [{"metric": "Price", "values": []}]})
    )
    await _provider().get_recent_prices("DANLAW", limit=400)
    assert route.calls.last.request.url.params["period"] == "3yr"


@pytest.mark.asyncio
@respx.mock
async def test_get_recent_prices_translates_provider_error():
    respx.get(f"{BASE_URL}/historical_data").mock(return_value=httpx.Response(401, text="unauthorized"))
    with pytest.raises(MarketProviderError) as exc_info:
        await _provider().get_recent_prices("DANLAW", limit=30)
    assert exc_info.value.code == MarketDataErrorCode.AUTHENTICATION_FAILED
