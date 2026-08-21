import httpx
import pytest
import respx

from app.market.exceptions import MarketProviderError
from app.market.providers.fmp_client import FMPMarketClient
from app.models.market import MarketDataErrorCode

BASE_URL = "http://test-fmp:9999/api"


def _client(**overrides) -> FMPMarketClient:
    defaults = dict(base_url=BASE_URL, api_key="test-key", max_retries=1)
    defaults.update(overrides)
    return FMPMarketClient(**defaults)


def test_requires_base_url():
    with pytest.raises(ValueError):
        FMPMarketClient(base_url="", api_key="key")


def test_requires_api_key():
    with pytest.raises(ValueError):
        FMPMarketClient(base_url=BASE_URL, api_key="")


@pytest.mark.asyncio
@respx.mock
async def test_get_quote_success():
    respx.get(f"{BASE_URL}/quote").mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "price": 180.5}])
    )
    data = await _client().get_quote("AAPL")
    assert data == {"symbol": "AAPL", "price": 180.5}


@pytest.mark.asyncio
@respx.mock
async def test_get_quote_empty_list_raises_ticker_not_found():
    respx.get(f"{BASE_URL}/quote").mock(return_value=httpx.Response(200, json=[]))
    with pytest.raises(MarketProviderError) as exc_info:
        await _client().get_quote("BOGUS")
    assert exc_info.value.code == MarketDataErrorCode.TICKER_NOT_FOUND


@pytest.mark.asyncio
@respx.mock
async def test_get_historical_prices_respects_limit():
    records = [{"date": f"2026-01-{day:02d}", "close": day} for day in range(1, 21)]
    respx.get(f"{BASE_URL}/historical-price-eod/full").mock(return_value=httpx.Response(200, json=records))
    data = await _client().get_historical_prices("AAPL", limit=5)
    assert len(data) == 5


@pytest.mark.asyncio
@respx.mock
async def test_sends_api_key_and_symbol_params():
    route = respx.get(f"{BASE_URL}/quote").mock(return_value=httpx.Response(200, json=[{"price": 1}]))
    await _client(api_key="secret-key").get_quote("MSFT")

    request = route.calls.last.request
    assert request.url.params["apikey"] == "secret-key"
    assert request.url.params["symbol"] == "MSFT"


@pytest.mark.asyncio
@respx.mock
async def test_401_raises_authentication_failed():
    respx.get(f"{BASE_URL}/quote").mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
    with pytest.raises(MarketProviderError) as exc_info:
        await _client().get_quote("AAPL")
    assert exc_info.value.code == MarketDataErrorCode.AUTHENTICATION_FAILED


@pytest.mark.asyncio
@respx.mock
async def test_404_raises_ticker_not_found():
    respx.get(f"{BASE_URL}/quote").mock(return_value=httpx.Response(404))
    with pytest.raises(MarketProviderError) as exc_info:
        await _client().get_quote("AAPL")
    assert exc_info.value.code == MarketDataErrorCode.TICKER_NOT_FOUND


@pytest.mark.asyncio
@respx.mock
async def test_429_without_retryable_wait_raises_rate_limited():
    respx.get(f"{BASE_URL}/quote").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "9999"})
    )
    with pytest.raises(MarketProviderError) as exc_info:
        await _client(max_retries=0).get_quote("AAPL")
    assert exc_info.value.code == MarketDataErrorCode.RATE_LIMITED
    assert exc_info.value.retry_after == 9999.0


@pytest.mark.asyncio
@respx.mock
async def test_500_retries_then_raises_provider_unavailable():
    respx.get(f"{BASE_URL}/quote").mock(return_value=httpx.Response(500))
    with pytest.raises(MarketProviderError) as exc_info:
        await _client(max_retries=1).get_quote("AAPL")
    assert exc_info.value.code == MarketDataErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
@respx.mock
async def test_malformed_json_raises_invalid_response():
    respx.get(f"{BASE_URL}/quote").mock(
        return_value=httpx.Response(200, content=b"not json", headers={"Content-Type": "application/json"})
    )
    with pytest.raises(MarketProviderError) as exc_info:
        await _client().get_quote("AAPL")
    assert exc_info.value.code == MarketDataErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
@respx.mock
async def test_non_list_response_raises_schema_mismatch():
    respx.get(f"{BASE_URL}/quote").mock(return_value=httpx.Response(200, json={"not": "a list"}))
    with pytest.raises(MarketProviderError) as exc_info:
        await _client().get_quote("AAPL")
    assert exc_info.value.code == MarketDataErrorCode.SCHEMA_MISMATCH


@pytest.mark.asyncio
@respx.mock
async def test_timeout_raises_provider_unavailable():
    respx.get(f"{BASE_URL}/quote").mock(side_effect=httpx.ConnectTimeout("timed out"))
    with pytest.raises(MarketProviderError) as exc_info:
        await _client(max_retries=0).get_quote("AAPL")
    assert exc_info.value.code == MarketDataErrorCode.PROVIDER_UNAVAILABLE
