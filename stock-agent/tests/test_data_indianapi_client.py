import httpx
import pytest
import respx

from app.data.exceptions import ProviderError
from app.data.models import FinancialDataErrorCode
from app.data.providers.indianapi_client import IndianAPIClient

BASE_URL = "http://test-indianapi:9999"


def _client(**overrides) -> IndianAPIClient:
    defaults = dict(base_url=BASE_URL, api_key="test-key", max_retries=1)
    defaults.update(overrides)
    return IndianAPIClient(**defaults)


def test_requires_base_url():
    with pytest.raises(ValueError):
        IndianAPIClient(base_url="", api_key="key")


def test_requires_api_key():
    with pytest.raises(ValueError):
        IndianAPIClient(base_url=BASE_URL, api_key="")


@pytest.mark.asyncio
@respx.mock
async def test_successful_response_returns_dict():
    respx.get(f"{BASE_URL}/stock").mock(
        return_value=httpx.Response(200, json={"companyName": "Acme", "financials": []})
    )
    data = await _client().get_stock("Acme")
    assert data == {"companyName": "Acme", "financials": []}


@pytest.mark.asyncio
@respx.mock
async def test_sends_api_key_header_and_name_param():
    route = respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(200, json={"financials": []}))
    await _client(api_key="secret-key").get_stock("Reliance")

    request = route.calls.last.request
    assert request.headers["X-Api-Key"] == "secret-key"
    assert request.url.params["name"] == "Reliance"


@pytest.mark.asyncio
@respx.mock
async def test_get_historical_prices_sends_period_and_filter_params():
    route = respx.get(f"{BASE_URL}/historical_data").mock(
        return_value=httpx.Response(200, json={"datasets": [{"metric": "Price", "values": []}]})
    )
    data = await _client().get_historical_prices("Danlaw", period="3yr")

    assert data == {"datasets": [{"metric": "Price", "values": []}]}
    request = route.calls.last.request
    assert request.url.params["stock_name"] == "Danlaw"
    assert request.url.params["period"] == "3yr"
    assert request.url.params["filter"] == "price"


@pytest.mark.asyncio
@respx.mock
async def test_get_historical_prices_error_body_raises_company_not_found():
    respx.get(f"{BASE_URL}/historical_data").mock(return_value=httpx.Response(200, json={"error": "not found"}))
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_historical_prices("Nonexistent")
    assert exc_info.value.code == FinancialDataErrorCode.COMPANY_NOT_FOUND


@pytest.mark.asyncio
@respx.mock
async def test_200_with_error_body_raises_company_not_found():
    # Verified live: an unmatched company name returns HTTP 200 with an
    # {"error": ...} body, not a 404.
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(200, json={"error": "Stock not found"}))
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_stock("NOT A REAL COMPANY")
    assert exc_info.value.code is FinancialDataErrorCode.COMPANY_NOT_FOUND


@pytest.mark.asyncio
@respx.mock
async def test_401_raises_authentication_failed():
    # Verified live: invalid key returns a plain-text (non-JSON) body.
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(401, text="Invalid API key"))
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.AUTHENTICATION_FAILED


@pytest.mark.asyncio
@respx.mock
async def test_403_raises_authentication_failed():
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(403, text="Forbidden"))
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.AUTHENTICATION_FAILED


@pytest.mark.asyncio
@respx.mock
async def test_404_raises_company_not_found():
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(404))
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.COMPANY_NOT_FOUND


@pytest.mark.asyncio
@respx.mock
async def test_429_without_retry_after_raises_rate_limited_immediately():
    route = respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(429))
    with pytest.raises(ProviderError) as exc_info:
        await _client(max_retries=2).get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.RATE_LIMITED
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_500_retries_then_raises_provider_unavailable():
    route = respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(500))
    with pytest.raises(ProviderError) as exc_info:
        await _client(max_retries=1).get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.PROVIDER_UNAVAILABLE
    assert route.call_count == 2  # initial + 1 retry


@pytest.mark.asyncio
@respx.mock
async def test_502_retries_then_raises_provider_unavailable():
    route = respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(502))
    with pytest.raises(ProviderError) as exc_info:
        await _client(max_retries=1).get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.PROVIDER_UNAVAILABLE
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_503_retries_then_raises_provider_unavailable():
    route = respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(503))
    with pytest.raises(ProviderError) as exc_info:
        await _client(max_retries=1).get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.PROVIDER_UNAVAILABLE
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_timeout_retries_then_raises_provider_unavailable():
    respx.get(f"{BASE_URL}/stock").mock(side_effect=httpx.TimeoutException("timed out"))
    with pytest.raises(ProviderError) as exc_info:
        await _client(max_retries=1).get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
@respx.mock
async def test_connection_error_raises_provider_unavailable():
    respx.get(f"{BASE_URL}/stock").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ProviderError) as exc_info:
        await _client(max_retries=0).get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
@respx.mock
async def test_malformed_json_raises_invalid_response():
    respx.get(f"{BASE_URL}/stock").mock(
        return_value=httpx.Response(200, content=b"not json", headers={"Content-Type": "application/json"})
    )
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
@respx.mock
async def test_empty_response_body_raises_invalid_response():
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(200, content=b""))
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
@respx.mock
async def test_non_object_schema_raises_schema_mismatch():
    respx.get(f"{BASE_URL}/stock").mock(return_value=httpx.Response(200, json=[1, 2, 3]))
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_stock("Reliance")
    assert exc_info.value.code is FinancialDataErrorCode.SCHEMA_MISMATCH
