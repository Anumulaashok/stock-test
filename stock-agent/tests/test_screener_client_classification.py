"""Screener failures must classify into explicit states so the source
manager can decide between retrying and falling back — an expired cookie
is not a timeout, and neither should surface as a generic error."""

import httpx
import pytest
import respx

from app.data.providers.screener_client import ScreenerClient, ScreenerImportError
from app.sources.provenance import SourceStatus
from app.sources.screener_health import validate_cookie

BASE_URL = "http://test-screener:9999"
SEARCH_PATH = f"{BASE_URL}/api/company/search/"
CHART_PATH = f"{BASE_URL}/api/company/1298/chart/"


def _client(**overrides) -> ScreenerClient:
    defaults = dict(base_url=BASE_URL, session_cookie="test-cookie", max_retries=1)
    defaults.update(overrides)
    return ScreenerClient(**defaults)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Retry backoff must not slow the suite down."""

    async def _instant(_seconds):
        return None

    monkeypatch.setattr("app.data.providers.screener_client.asyncio.sleep", _instant)


# --- Cookie presence ---------------------------------------------------------


def test_cookie_missing_is_visible_without_a_request():
    assert not ScreenerClient(base_url=BASE_URL).has_cookie
    assert _client().has_cookie


@respx.mock
async def test_cookie_is_sent_as_a_session_header_and_never_in_the_url():
    route = respx.get(SEARCH_PATH).mock(return_value=httpx.Response(200, json=[]))
    await _client().search_companies("reliance")
    request = route.calls[0].request
    assert request.headers["Cookie"] == "sessionid=test-cookie"
    assert "test-cookie" not in str(request.url)


# --- Status classification ---------------------------------------------------


@pytest.mark.parametrize("code", [401, 403])
@respx.mock
async def test_auth_failures_classify_as_auth_expired(code):
    respx.get(SEARCH_PATH).mock(return_value=httpx.Response(code))
    with pytest.raises(ScreenerImportError) as exc:
        await _client().search_companies("reliance")
    assert exc.value.status == SourceStatus.AUTH_EXPIRED


@pytest.mark.parametrize("code", [401, 403])
@respx.mock
async def test_auth_failures_are_never_retried(code):
    """Retrying an expired cookie only burns time before the fallback."""
    route = respx.get(SEARCH_PATH).mock(return_value=httpx.Response(code))
    with pytest.raises(ScreenerImportError):
        await _client(max_retries=3).search_companies("reliance")
    assert route.call_count == 1


@respx.mock
async def test_rate_limit_classifies_and_respects_retry_after():
    route = respx.get(SEARCH_PATH).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(200, json=[]),
        ]
    )
    assert await _client().search_companies("reliance") == []
    assert route.call_count == 2


@respx.mock
async def test_persistent_rate_limit_surfaces_as_rate_limited():
    respx.get(SEARCH_PATH).mock(return_value=httpx.Response(429))
    with pytest.raises(ScreenerImportError) as exc:
        await _client().search_companies("reliance")
    assert exc.value.status == SourceStatus.RATE_LIMITED


@respx.mock
async def test_timeout_is_retried_then_classified_as_unreachable():
    route = respx.get(SEARCH_PATH).mock(side_effect=httpx.ConnectTimeout("timed out"))
    with pytest.raises(ScreenerImportError) as exc:
        await _client(max_retries=2).search_companies("reliance")
    assert exc.value.status == SourceStatus.UNREACHABLE
    assert route.call_count == 3


@respx.mock
async def test_transient_network_error_recovers_on_retry():
    route = respx.get(CHART_PATH).mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json={"datasets": []})]
    )
    assert await _client().get_chart(1298) == {"datasets": []}
    assert route.call_count == 2


@respx.mock
async def test_server_error_is_unreachable_not_invalid():
    respx.get(CHART_PATH).mock(return_value=httpx.Response(503))
    with pytest.raises(ScreenerImportError) as exc:
        await _client().get_chart(1298)
    assert exc.value.status == SourceStatus.UNREACHABLE


@respx.mock
async def test_malformed_json_classifies_as_invalid_and_is_not_retried():
    route = respx.get(CHART_PATH).mock(
        return_value=httpx.Response(200, content=b"<html>not json</html>")
    )
    with pytest.raises(ScreenerImportError) as exc:
        await _client(max_retries=2).get_chart(1298)
    assert exc.value.status == SourceStatus.INVALID
    assert route.call_count == 1


@respx.mock
async def test_wrong_json_shape_classifies_as_invalid():
    respx.get(SEARCH_PATH).mock(return_value=httpx.Response(200, json={"not": "a list"}))
    with pytest.raises(ScreenerImportError) as exc:
        await _client().search_companies("reliance")
    assert exc.value.status == SourceStatus.INVALID


@respx.mock
async def test_client_error_classifies_as_invalid():
    respx.get(CHART_PATH).mock(return_value=httpx.Response(404))
    with pytest.raises(ScreenerImportError) as exc:
        await _client().get_chart(1298)
    assert exc.value.status == SourceStatus.INVALID


# --- Cookie health lifecycle -------------------------------------------------


async def test_unconfigured_cookie_reports_not_configured_without_calling_screener():
    health = await validate_cookie(ScreenerClient(base_url=BASE_URL), source=None)
    assert health.status == SourceStatus.NOT_CONFIGURED
    assert health.configured is False


@respx.mock
async def test_valid_cookie_records_success_timestamps():
    respx.get(SEARCH_PATH).mock(return_value=httpx.Response(200, json=[]))
    health = await validate_cookie(_client(), source="runtime")
    assert health.status == SourceStatus.SUCCESS
    assert health.configured is True
    assert health.source == "runtime"
    assert health.last_success_at is not None
    assert health.last_error_at is None


@respx.mock
async def test_expired_cookie_reports_auth_expired_rather_than_raising():
    respx.get(SEARCH_PATH).mock(return_value=httpx.Response(403))
    health = await validate_cookie(_client(), source="runtime")
    assert health.status == SourceStatus.AUTH_EXPIRED
    assert health.last_error_at is not None
    assert health.last_success_at is None


@respx.mock
async def test_screener_outage_is_not_reported_as_an_expired_cookie():
    """A user whose cookie is fine must not be told to re-authenticate
    because Screener happened to be down."""
    respx.get(SEARCH_PATH).mock(return_value=httpx.Response(502))
    health = await validate_cookie(_client(), source="env")
    assert health.status == SourceStatus.UNREACHABLE
    assert "could not be reached" in health.detail


@respx.mock
async def test_validation_never_leaks_the_cookie_value():
    respx.get(SEARCH_PATH).mock(return_value=httpx.Response(403))
    health = await validate_cookie(_client(), source="runtime")
    assert "test-cookie" not in health.model_dump_json()


@respx.mock
async def test_validation_is_a_single_cheap_request():
    route = respx.get(SEARCH_PATH).mock(return_value=httpx.Response(200, json=[]))
    await validate_cookie(_client(), source="runtime")
    assert route.call_count == 1
