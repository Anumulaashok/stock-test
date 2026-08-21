import httpx
import pytest
import respx

from app.models.research import ResearchErrorCode
from app.research.exceptions import ResearchProviderError
from app.research.providers.finnhub_client import FinnhubClient

BASE_URL = "http://test-finnhub:9999/api/v1"


def _client(**overrides) -> FinnhubClient:
    defaults = dict(base_url=BASE_URL, api_key="test-key", max_retries=1)
    defaults.update(overrides)
    return FinnhubClient(**defaults)


def test_requires_base_url():
    with pytest.raises(ValueError):
        FinnhubClient(base_url="", api_key="key")


def test_requires_api_key():
    with pytest.raises(ValueError):
        FinnhubClient(base_url=BASE_URL, api_key="")


@pytest.mark.asyncio
@respx.mock
async def test_successful_response():
    respx.get(f"{BASE_URL}/company-news").mock(
        return_value=httpx.Response(200, json=[{"headline": "News", "url": "https://x.com/1"}])
    )
    data = await _client().get_company_news("AAPL", "2026-01-01", "2026-01-31")
    assert data == [{"headline": "News", "url": "https://x.com/1"}]


@pytest.mark.asyncio
@respx.mock
async def test_no_results_returns_empty_list():
    respx.get(f"{BASE_URL}/company-news").mock(return_value=httpx.Response(200, json=[]))
    data = await _client().get_company_news("AAPL", "2026-01-01", "2026-01-31")
    assert data == []


@pytest.mark.asyncio
@respx.mock
async def test_sends_token_and_query_params():
    route = respx.get(f"{BASE_URL}/company-news").mock(return_value=httpx.Response(200, json=[]))
    await _client(api_key="secret-token").get_company_news("AAPL", "2026-01-01", "2026-01-31")

    request = route.calls.last.request
    assert request.url.params["token"] == "secret-token"
    assert request.url.params["symbol"] == "AAPL"
    assert request.url.params["from"] == "2026-01-01"
    assert request.url.params["to"] == "2026-01-31"


@pytest.mark.asyncio
@respx.mock
async def test_401_raises_authentication_failed():
    respx.get(f"{BASE_URL}/company-news").mock(return_value=httpx.Response(401))
    with pytest.raises(ResearchProviderError) as exc_info:
        await _client().get_company_news("AAPL", "2026-01-01", "2026-01-31")
    assert exc_info.value.code is ResearchErrorCode.AUTHENTICATION_FAILED


@pytest.mark.asyncio
@respx.mock
async def test_403_raises_authentication_failed():
    respx.get(f"{BASE_URL}/company-news").mock(return_value=httpx.Response(403))
    with pytest.raises(ResearchProviderError) as exc_info:
        await _client().get_company_news("AAPL", "2026-01-01", "2026-01-31")
    assert exc_info.value.code is ResearchErrorCode.AUTHENTICATION_FAILED


@pytest.mark.asyncio
@respx.mock
async def test_404_raises_invalid_response():
    respx.get(f"{BASE_URL}/company-news").mock(return_value=httpx.Response(404))
    with pytest.raises(ResearchProviderError) as exc_info:
        await _client().get_company_news("AAPL", "2026-01-01", "2026-01-31")
    assert exc_info.value.code is ResearchErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
@respx.mock
async def test_429_without_retry_after_raises_rate_limited():
    respx.get(f"{BASE_URL}/company-news").mock(return_value=httpx.Response(429))
    with pytest.raises(ResearchProviderError) as exc_info:
        await _client(max_retries=2).get_company_news("AAPL", "2026-01-01", "2026-01-31")
    assert exc_info.value.code is ResearchErrorCode.RATE_LIMITED


@pytest.mark.asyncio
@respx.mock
async def test_5xx_retries_then_raises_provider_unavailable():
    route = respx.get(f"{BASE_URL}/company-news").mock(return_value=httpx.Response(503))
    with pytest.raises(ResearchProviderError) as exc_info:
        await _client(max_retries=2).get_company_news("AAPL", "2026-01-01", "2026-01-31")
    assert exc_info.value.code is ResearchErrorCode.PROVIDER_UNAVAILABLE
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_timeout_raises_provider_unavailable():
    respx.get(f"{BASE_URL}/company-news").mock(side_effect=httpx.TimeoutException("timed out"))
    with pytest.raises(ResearchProviderError) as exc_info:
        await _client(max_retries=0).get_company_news("AAPL", "2026-01-01", "2026-01-31")
    assert exc_info.value.code is ResearchErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
@respx.mock
async def test_connection_error_raises_provider_unavailable():
    respx.get(f"{BASE_URL}/company-news").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ResearchProviderError) as exc_info:
        await _client(max_retries=0).get_company_news("AAPL", "2026-01-01", "2026-01-31")
    assert exc_info.value.code is ResearchErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
@respx.mock
async def test_malformed_json_raises_invalid_response():
    respx.get(f"{BASE_URL}/company-news").mock(
        return_value=httpx.Response(200, content=b"not json", headers={"Content-Type": "application/json"})
    )
    with pytest.raises(ResearchProviderError) as exc_info:
        await _client().get_company_news("AAPL", "2026-01-01", "2026-01-31")
    assert exc_info.value.code is ResearchErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
@respx.mock
async def test_non_list_schema_raises_invalid_response():
    respx.get(f"{BASE_URL}/company-news").mock(return_value=httpx.Response(200, json={"error": "bad"}))
    with pytest.raises(ResearchProviderError) as exc_info:
        await _client().get_company_news("AAPL", "2026-01-01", "2026-01-31")
    assert exc_info.value.code is ResearchErrorCode.INVALID_RESPONSE
