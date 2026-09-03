"""The status endpoint must distinguish four different things: a source
being configured, being capable of a category, being the active choice
for it, and currently working."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)

SEARCH_URL = "https://www.screener.in/api/company/search/"
ENDPOINT = "/api/v1/market/data-sources/status"


@pytest.fixture(autouse=True)
def _db_override(db_dependency_override):
    yield


def _by_name(body) -> dict:
    return {source["name"]: source for source in body["sources"]}


def test_status_reports_capabilities_and_roles(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "")
    monkeypatch.setenv("INDIAN_API_KEY", "test-key")
    get_settings.cache_clear()

    response = client.get(ENDPOINT)
    get_settings.cache_clear()

    assert response.status_code == 200
    sources = _by_name(response.json())

    assert sources["yfinance"]["primary_for"] == ["market_quote"]
    assert "quote" in sources["yfinance"]["capabilities"]
    assert sources["indianapi"]["configured"] is True


def test_screener_never_claims_financial_statement_capability(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "")
    get_settings.cache_clear()

    sources = _by_name(client.get(ENDPOINT).json())
    get_settings.cache_clear()

    capabilities = sources["screener"]["capabilities"]
    assert "income_statement" not in capabilities
    assert "balance_sheet" not in capabilities
    assert "cash_flow" not in capabilities
    # Close-only series, honestly labelled.
    assert "daily_close_series" in capabilities
    assert "ohlcv" not in capabilities


def test_unconfigured_source_is_reported_as_unconfigured_not_healthy(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "")
    get_settings.cache_clear()

    sources = _by_name(client.get(ENDPOINT).json())
    get_settings.cache_clear()

    assert sources["screener"]["configured"] is False
    assert sources["screener"]["status"] == "NOT_CONFIGURED"
    # Still reports the role it would play once configured.
    assert "historical_price" in sources["screener"]["primary_for"]


@respx.mock
def test_expired_screener_cookie_surfaces_in_the_status_endpoint(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "stale-cookie")
    get_settings.cache_clear()
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(403))

    response = client.get(ENDPOINT)
    get_settings.cache_clear()

    sources = _by_name(response.json())
    assert sources["screener"]["configured"] is True
    assert sources["screener"]["status"] == "AUTH_EXPIRED"
    assert "stale-cookie" not in response.text


@respx.mock
def test_valid_screener_cookie_reports_success(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "good-cookie")
    get_settings.cache_clear()
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=[]))

    sources = _by_name(client.get(ENDPOINT).json())
    get_settings.cache_clear()

    assert sources["screener"]["status"] == "SUCCESS"


def test_fmp_limitation_is_disclosed_rather_than_reported_as_a_healthy_fallback(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "")
    get_settings.cache_clear()

    sources = _by_name(client.get(ENDPOINT).json())
    get_settings.cache_clear()

    assert sources["fmp"]["configured"] is True
    # Configured and capable, but the NSE constraint is stated outright.
    assert "402" in sources["fmp"]["limitation"]


def test_no_secrets_are_returned(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "")
    monkeypatch.setenv("INDIAN_API_KEY", "super-secret-indianapi-key")
    monkeypatch.setenv("FMP_API_KEY", "super-secret-fmp-key")
    get_settings.cache_clear()

    text = client.get(ENDPOINT).text
    get_settings.cache_clear()

    assert "super-secret-indianapi-key" not in text
    assert "super-secret-fmp-key" not in text
