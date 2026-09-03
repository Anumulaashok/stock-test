import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _db_override(db_dependency_override):
    yield


_SCREENER_CHART_RESPONSE = {
    "datasets": [
        {"metric": "Price", "values": [["2026-09-02", "178.35"], ["2026-09-03", "181.07"]]},
        {"metric": "DMA50", "values": [["2026-09-03", "194.04"]]},
        {"metric": "DMA200", "values": [["2026-09-03", "202.90"]]},
        {"metric": "Volume", "values": [["2026-09-03", 5698964, {"delivery": None}]]},
    ]
}


@respx.mock
def test_import_endpoint_stores_rows_and_returns_summary():
    respx.get("https://www.screener.in/api/company/1298/chart/").mock(
        return_value=httpx.Response(200, json=_SCREENER_CHART_RESPONSE)
    )

    response = client.post(
        "/api/v1/market/HDFCBANK/historical/import",
        json={"screener_company_id": 1298, "days": 365, "consolidated": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "HDFCBANK"
    assert body["rows_imported"] == 2
    assert body["earliest_date"] == "2026-09-02"
    assert body["latest_date"] == "2026-09-03"


@respx.mock
def test_import_endpoint_degrades_instead_of_failing_when_screener_is_down():
    """A Screener outage used to abort the import with a 502. It must now
    classify, try the configured fallback, and return a structured result
    saying what actually happened."""
    respx.get("https://www.screener.in/api/company/9999/chart/").mock(
        return_value=httpx.Response(500)
    )

    response = client.post(
        "/api/v1/market/HDFCBANK/historical/import",
        json={"screener_company_id": 9999},
    )

    assert response.status_code == 200
    body = response.json()
    # No fallback can reach the network in this test, so the honest answer
    # is UNAVAILABLE with zero rows -- never a fabricated import.
    assert body["status"] in {"FALLBACK", "UNAVAILABLE"}
    assert body["ticker"] == "HDFCBANK"
    if body["status"] == "UNAVAILABLE":
        assert body["rows_imported"] == 0
        assert "UNREACHABLE" in body["detail"]


@respx.mock
def test_forecast_accuracy_endpoint_returns_empty_summary_when_nothing_stored():
    response = client.get("/api/v1/market/HDFCBANK/forecast-accuracy")

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "HDFCBANK"
    assert body["evaluated_count"] == 0
    assert body["entries"] == []


@respx.mock
def test_import_then_re_import_updates_existing_rows_not_duplicates():
    respx.get("https://www.screener.in/api/company/1298/chart/").mock(
        return_value=httpx.Response(200, json=_SCREENER_CHART_RESPONSE)
    )
    first = client.post(
        "/api/v1/market/HDFCBANK/historical/import", json={"screener_company_id": 1298}
    )
    second = client.post(
        "/api/v1/market/HDFCBANK/historical/import", json={"screener_company_id": 1298}
    )

    assert first.json()["rows_imported"] == 2
    assert second.json()["rows_imported"] == 2  # re-import updates the same 2 rows, not 4


# --- screener-mappings: bulk import + autocomplete search ----------------------------

_COMPANY_SEARCH_RESPONSE = [
    {"id": 681, "name": "Coal India Ltd", "url": "/company/COALINDIA/consolidated/"},
    {"id": 685, "name": "Colgate-Palmolive (India) Ltd", "url": "/company/COLPAL/"},
    {"id": None, "name": "Search everywhere: co", "url": "/full-text-search/?q=co"},
]


def test_mapping_bulk_import_registers_and_skips_sentinel_row():
    response = client.post("/api/v1/market/screener-mappings/import", json={"companies": _COMPANY_SEARCH_RESPONSE})

    assert response.status_code == 200
    body = response.json()
    assert body["registered"] == 2
    assert body["skipped"] == 1


def test_mapping_search_finds_by_ticker_after_bulk_import():
    client.post("/api/v1/market/screener-mappings/import", json={"companies": _COMPANY_SEARCH_RESPONSE})

    response = client.get("/api/v1/market/screener-mappings", params={"q": "COAL"})

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["ticker"] == "COALINDIA"
    assert results[0]["screener_company_id"] == 681
    assert results[0]["company_name"] == "Coal India Ltd"


def test_mapping_search_finds_by_company_name():
    client.post("/api/v1/market/screener-mappings/import", json={"companies": _COMPANY_SEARCH_RESPONSE})

    response = client.get("/api/v1/market/screener-mappings", params={"q": "Colgate"})

    assert response.status_code == 200
    results = response.json()
    assert results[0]["ticker"] == "COLPAL"


@respx.mock
def test_import_reuses_registered_mapping_when_id_omitted():
    client.post("/api/v1/market/screener-mappings/import", json={"companies": _COMPANY_SEARCH_RESPONSE})
    respx.get("https://www.screener.in/api/company/681/chart/").mock(
        return_value=httpx.Response(200, json=_SCREENER_CHART_RESPONSE)
    )

    response = client.post("/api/v1/market/COALINDIA/historical/import", json={})

    assert response.status_code == 200
    assert response.json()["rows_imported"] == 2


def test_import_without_id_or_mapping_returns_400():
    response = client.post("/api/v1/market/UNMAPPEDTICKER/historical/import", json={})

    assert response.status_code == 400


# --- company-search: cookie-configured (screener) vs fallback (local directory) -----

_HDFC_SEARCH_RESPONSE = [
    {"id": 1298, "name": "HDFC Bank Ltd", "url": "/company/HDFCBANK/consolidated/"},
    {"id": None, "name": "Search everywhere: HDFC", "url": "/full-text-search/?q=HDFC"},
]


@respx.mock
def test_company_search_uses_screener_when_cookie_configured(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "test-session-cookie")
    get_settings.cache_clear()
    respx.get("https://www.screener.in/api/company/search/").mock(
        return_value=httpx.Response(200, json=_HDFC_SEARCH_RESPONSE)
    )

    response = client.get("/api/v1/market/company-search", params={"q": "HDFC"})
    get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "screener"
    assert body["results"][0]["ticker"] == "HDFCBANK"
    assert body["results"][0]["screener_company_id"] == 1298

    # also auto-registered as a mapping
    mapping_response = client.get("/api/v1/market/screener-mappings", params={"q": "HDFCBANK"})
    assert mapping_response.json()[0]["screener_company_id"] == 1298


def test_company_search_falls_back_to_local_directory_without_cookie(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "")
    get_settings.cache_clear()

    response = client.get("/api/v1/market/company-search", params={"q": "RELIANCE"})
    get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "local_directory"
    assert all(r["source"] == "local_directory" for r in body["results"])
    assert all(r["screener_company_id"] is None for r in body["results"])


@respx.mock
def test_company_search_falls_back_when_screener_request_fails(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "test-session-cookie")
    get_settings.cache_clear()
    respx.get("https://www.screener.in/api/company/search/").mock(return_value=httpx.Response(500))

    response = client.get("/api/v1/market/company-search", params={"q": "RELIANCE"})
    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["source"] == "local_directory"


# --- runtime-editable Screener cookie settings ----------------------------------------


_SEARCH_URL = "https://www.screener.in/api/company/search/"


def test_cookie_status_reports_unconfigured_by_default(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "")
    get_settings.cache_clear()

    response = client.get("/api/v1/market/settings/screener-cookie")
    get_settings.cache_clear()

    body = response.json()
    assert body["configured"] is False
    assert body["source"] is None
    assert body["status"] == "NOT_CONFIGURED"


def test_cookie_status_reports_env_when_only_env_set(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "env-cookie-value")
    get_settings.cache_clear()

    response = client.get("/api/v1/market/settings/screener-cookie")
    get_settings.cache_clear()

    body = response.json()
    assert body["configured"] is True
    assert body["source"] == "env"
    # Not validated unless explicitly asked, so page loads stay cheap.
    assert body["status"] == "UNKNOWN"


@respx.mock
def test_cookie_status_validates_only_when_asked(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "env-cookie-value")
    get_settings.cache_clear()
    route = respx.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json=[]))

    client.get("/api/v1/market/settings/screener-cookie")
    assert route.call_count == 0

    response = client.get("/api/v1/market/settings/screener-cookie?validate=true")
    get_settings.cache_clear()

    assert route.call_count == 1
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["last_success_at"] is not None


@respx.mock
def test_expired_cookie_is_reported_as_auth_expired(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "")
    get_settings.cache_clear()
    respx.get(_SEARCH_URL).mock(return_value=httpx.Response(403))

    response = client.put(
        "/api/v1/market/settings/screener-cookie", json={"session_cookie": "stale-value"}
    )
    get_settings.cache_clear()

    body = response.json()
    # Saved regardless -- the user gets told it is expired, not silently refused.
    assert body["configured"] is True
    assert body["status"] == "AUTH_EXPIRED"
    assert "stale-value" not in response.text


@respx.mock
def test_set_cookie_takes_effect_without_restart_and_clear_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "env-cookie-value")
    get_settings.cache_clear()
    respx.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json=[]))

    set_response = client.put("/api/v1/market/settings/screener-cookie", json={"session_cookie": "runtime-value"})
    assert set_response.json()["source"] == "runtime"
    assert set_response.json()["configured"] is True
    assert "runtime-value" not in set_response.text

    status_response = client.get("/api/v1/market/settings/screener-cookie")
    assert status_response.json()["source"] == "runtime"

    clear_response = client.delete("/api/v1/market/settings/screener-cookie")
    get_settings.cache_clear()
    assert clear_response.json() == {
        "configured": True,
        "source": "env",
        "status": "UNKNOWN",
        "last_validated_at": None,
        "last_success_at": None,
        "last_error_at": None,
        "detail": None,
    }


@respx.mock
def test_clear_cookie_with_no_env_reports_unconfigured(monkeypatch):
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", "")
    get_settings.cache_clear()
    respx.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json=[]))

    client.put("/api/v1/market/settings/screener-cookie", json={"session_cookie": "runtime-value"})
    response = client.delete("/api/v1/market/settings/screener-cookie")
    get_settings.cache_clear()

    body = response.json()
    assert body["configured"] is False
    assert body["source"] is None


# --- real Nifty 50 / Sensex index quotes ----------------------------------------------


def test_indices_endpoint_returns_unavailable_when_no_market_provider(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "fmp")
    monkeypatch.setenv("FMP_API_KEY", "")
    get_settings.cache_clear()

    response = client.get("/api/v1/market/indices")
    get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body["indices"]) == 2
    assert all(i["status"] == "unavailable" for i in body["indices"])
    assert {i["symbol"] for i in body["indices"]} == {"^NSEI", "^BSESN"}
