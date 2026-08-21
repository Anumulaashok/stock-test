import httpx
import pytest
import respx

from app.data.exceptions import ProviderError
from app.data.models import FinancialDataErrorCode
from app.data.providers.fmp_client import FMPClient

BASE_URL = "http://test-fmp:9999/stable"


def _client(**overrides) -> FMPClient:
    defaults = dict(base_url=BASE_URL, api_key="test-key", max_retries=1)
    defaults.update(overrides)
    return FMPClient(**defaults)


def test_requires_base_url():
    with pytest.raises(ValueError):
        FMPClient(base_url="", api_key="key")


def test_requires_api_key():
    with pytest.raises(ValueError):
        FMPClient(base_url=BASE_URL, api_key="")


@pytest.mark.asyncio
@respx.mock
async def test_successful_response_returns_list():
    respx.get(f"{BASE_URL}/income-statement").mock(
        return_value=httpx.Response(200, json=[{"date": "2024-12-31", "period": "FY", "revenue": 100}])
    )
    data = await _client().get_income_statements("AAPL", limit=5)
    assert data == [{"date": "2024-12-31", "period": "FY", "revenue": 100}]


@pytest.mark.asyncio
@respx.mock
async def test_sends_api_key_and_query_params():
    route = respx.get(f"{BASE_URL}/income-statement").mock(return_value=httpx.Response(200, json=[]))
    await _client(api_key="secret-key").get_income_statements("AAPL", limit=5)

    request = route.calls.last.request
    assert request.url.params["apikey"] == "secret-key"
    assert request.url.params["symbol"] == "AAPL"
    assert request.url.params["period"] == "annual"
    assert request.url.params["limit"] == "5"


@pytest.mark.asyncio
@respx.mock
async def test_401_raises_authentication_failed():
    respx.get(f"{BASE_URL}/income-statement").mock(return_value=httpx.Response(401, json={"error": "bad key"}))
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_income_statements("AAPL", limit=5)
    assert exc_info.value.code is FinancialDataErrorCode.AUTHENTICATION_FAILED


@pytest.mark.asyncio
@respx.mock
async def test_403_raises_authentication_failed():
    respx.get(f"{BASE_URL}/income-statement").mock(return_value=httpx.Response(403))
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_income_statements("AAPL", limit=5)
    assert exc_info.value.code is FinancialDataErrorCode.AUTHENTICATION_FAILED


@pytest.mark.asyncio
@respx.mock
async def test_404_raises_company_not_found():
    respx.get(f"{BASE_URL}/income-statement").mock(return_value=httpx.Response(404))
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_income_statements("NOPE", limit=5)
    assert exc_info.value.code is FinancialDataErrorCode.COMPANY_NOT_FOUND


@pytest.mark.asyncio
@respx.mock
async def test_429_without_retry_after_raises_rate_limited_immediately():
    route = respx.get(f"{BASE_URL}/income-statement").mock(return_value=httpx.Response(429))
    with pytest.raises(ProviderError) as exc_info:
        await _client(max_retries=2).get_income_statements("AAPL", limit=5)
    assert exc_info.value.code is FinancialDataErrorCode.RATE_LIMITED
    assert route.call_count == 1  # no retry without a usable Retry-After


@pytest.mark.asyncio
@respx.mock
async def test_429_respects_small_retry_after_then_succeeds():
    route = respx.get(f"{BASE_URL}/income-statement").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json=[{"date": "2024-12-31", "period": "FY"}]),
        ]
    )
    data = await _client(max_retries=1).get_income_statements("AAPL", limit=5)
    assert data == [{"date": "2024-12-31", "period": "FY"}]
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_429_with_large_retry_after_does_not_wait_that_long():
    respx.get(f"{BASE_URL}/income-statement").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "9999"})
    )
    with pytest.raises(ProviderError) as exc_info:
        await _client(max_retries=1).get_income_statements("AAPL", limit=5)
    assert exc_info.value.code is FinancialDataErrorCode.RATE_LIMITED


@pytest.mark.asyncio
@respx.mock
async def test_5xx_retries_then_raises_provider_unavailable():
    route = respx.get(f"{BASE_URL}/income-statement").mock(return_value=httpx.Response(503))
    with pytest.raises(ProviderError) as exc_info:
        await _client(max_retries=2).get_income_statements("AAPL", limit=5)
    assert exc_info.value.code is FinancialDataErrorCode.PROVIDER_UNAVAILABLE
    assert route.call_count == 3  # initial + 2 retries


@pytest.mark.asyncio
@respx.mock
async def test_5xx_retries_then_succeeds():
    route = respx.get(f"{BASE_URL}/income-statement").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json=[])]
    )
    data = await _client(max_retries=2).get_income_statements("AAPL", limit=5)
    assert data == []
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_timeout_retries_then_raises_provider_unavailable():
    respx.get(f"{BASE_URL}/income-statement").mock(side_effect=httpx.TimeoutException("timed out"))
    with pytest.raises(ProviderError) as exc_info:
        await _client(max_retries=1).get_income_statements("AAPL", limit=5)
    assert exc_info.value.code is FinancialDataErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
@respx.mock
async def test_connection_error_raises_provider_unavailable():
    respx.get(f"{BASE_URL}/income-statement").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ProviderError) as exc_info:
        await _client(max_retries=0).get_income_statements("AAPL", limit=5)
    assert exc_info.value.code is FinancialDataErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
@respx.mock
async def test_malformed_json_raises_invalid_response():
    respx.get(f"{BASE_URL}/income-statement").mock(
        return_value=httpx.Response(200, content=b"not json", headers={"Content-Type": "application/json"})
    )
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_income_statements("AAPL", limit=5)
    assert exc_info.value.code is FinancialDataErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
@respx.mock
async def test_non_list_schema_raises_schema_mismatch():
    respx.get(f"{BASE_URL}/income-statement").mock(
        return_value=httpx.Response(200, json={"error": "unexpected shape"})
    )
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_income_statements("AAPL", limit=5)
    assert exc_info.value.code is FinancialDataErrorCode.SCHEMA_MISMATCH


@pytest.mark.asyncio
@respx.mock
async def test_other_4xx_raises_invalid_response():
    respx.get(f"{BASE_URL}/income-statement").mock(return_value=httpx.Response(400))
    with pytest.raises(ProviderError) as exc_info:
        await _client().get_income_statements("AAPL", limit=5)
    assert exc_info.value.code is FinancialDataErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
@respx.mock
async def test_balance_sheet_and_cash_flow_endpoints_use_correct_paths():
    respx.get(f"{BASE_URL}/balance-sheet-statement").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{BASE_URL}/cash-flow-statement").mock(return_value=httpx.Response(200, json=[]))
    client = _client()
    assert await client.get_balance_sheets("AAPL", limit=5) == []
    assert await client.get_cash_flow_statements("AAPL", limit=5) == []
