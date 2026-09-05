"""API-level tests for `app.api.ml_forecast` -- schema shape and the
spec section 28 graceful-degradation path (no trained artifacts, no
network-reachable price provider) using the `db_client` fixture from
`tests/conftest.py` (in-memory SQLite, no lifespan DB connection)."""

import pytest

from app.market.providers.yfinance_client import YFinanceClient


@pytest.fixture(autouse=True)
def _no_network_price_history(monkeypatch):
    """Every ML forecast test in this module must never hit the real
    Yahoo Finance API -- simulate "provider unavailable" instead, which
    exercises the exact degraded-response path spec section 28 requires."""

    async def _fail(self, ticker, period):
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(YFinanceClient, "get_history", _fail)


def test_forecast_endpoint_degrades_gracefully_without_price_data(db_client):
    response = db_client.get("/api/v1/ml-forecast/NOPRICEHISTORY")
    assert response.status_code == 200
    body = response.json()

    assert body["ticker"] == "NOPRICEHISTORY"
    assert body["warnings"], "must explain why the forecast is empty"
    assert set(body["horizons"].keys()) == {"14D", "1M", "3M", "1Y"}

    for horizon_forecast in body["horizons"].values():
        assert horizon_forecast["forecast_quality"] == "LOW"
        assert horizon_forecast["analog"]["sample_size"] == 0
        assert horizon_forecast["analog"]["is_reliable"] is False

    assert body["news_impact"]["data_available"] is False
    assert body["model_version"] and body["feature_version"] and body["news_model_version"]


def test_forecast_response_never_claims_certainty_language(db_client):
    """Spec section 36: forbidden words must never appear anywhere in a
    served forecast, including quality reasons and driver text."""
    response = db_client.get("/api/v1/ml-forecast/NOPRICEHISTORY")
    body_text = response.text.lower()
    for forbidden in ("guaranteed", "will reach", "certain target", "safe return"):
        assert forbidden not in body_text


def test_accuracy_endpoint_reports_zero_sample_when_untrained(db_client):
    response = db_client.get("/api/v1/ml-forecast/RELIANCE/accuracy")
    assert response.status_code == 200
    body = response.json()
    assert set(body["accuracy_by_horizon"].keys()) == {"14D", "1M", "3M", "1Y"}
    for entry in body["accuracy_by_horizon"].values():
        assert entry["sample_size"] == 0


def test_history_endpoint_returns_empty_list_for_unknown_ticker(db_client):
    response = db_client.get("/api/v1/ml-forecast/NEVERPREDICTED/history")
    assert response.status_code == 200
    assert response.json()["predictions"] == []
