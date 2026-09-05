from decimal import Decimal

from app.api.alerts import get_alert_service
from app.alerts.service import AlertService
from app.main import app
from app.models.market import MarketDataError, MarketDataErrorCode, MarketQuote, MarketSnapshot, MarketSnapshotResult, MarketStatus, PriceFreshness


def _signup(db_client, email="alice@example.com", password="correct-horse"):
    return db_client.post("/api/v1/auth/signup", json={"email": email, "password": password})


def _auth_headers(db_client, email="alice@example.com") -> dict:
    token = _signup(db_client, email=email).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class _StubMarketDataService:
    def __init__(self, results: dict[str, MarketSnapshotResult]) -> None:
        self._results = results

    async def get_quote(self, ticker: str) -> MarketSnapshotResult:
        return self._results.get(
            ticker, MarketSnapshotResult(status="error", error=MarketDataError(code=MarketDataErrorCode.TICKER_NOT_FOUND, message="not found"))
        )


def _quote_result(ticker: str, price: str) -> MarketSnapshotResult:
    quote = MarketQuote(
        ticker=ticker, current_price=Decimal(price), previous_close=Decimal(price), change=Decimal(0), change_percent=Decimal(0),
        currency="INR", market_status=MarketStatus.OPEN, market_timestamp=None,
        data_timestamp="2026-08-21T00:00:00+00:00", freshness=PriceFreshness.LIVE, source="stub",
    )
    snapshot = MarketSnapshot(ticker=ticker, quote=quote, recent_prices=[], fetched_at="2026-08-21T00:00:00+00:00")
    return MarketSnapshotResult(status="success", snapshot=snapshot)


def _override_market(results: dict[str, MarketSnapshotResult]):
    app.dependency_overrides[get_alert_service] = lambda: AlertService(_StubMarketDataService(results))


def _clear_market_override():
    app.dependency_overrides.pop(get_alert_service, None)


def test_alerts_require_authentication(db_client):
    assert db_client.get("/api/v1/alerts").status_code == 401
    assert db_client.post("/api/v1/alerts", json={"ticker": "ACME", "condition_type": "PRICE_ABOVE", "threshold_value": "100"}).status_code == 401
    assert db_client.post("/api/v1/alerts/evaluate").status_code == 401


def test_alerts_start_empty(db_client):
    headers = _auth_headers(db_client)
    response = db_client.get("/api/v1/alerts", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_create_alert_returns_created_alert(db_client):
    headers = _auth_headers(db_client)
    response = db_client.post(
        "/api/v1/alerts", json={"ticker": "acme", "condition_type": "PRICE_ABOVE", "threshold_value": "100"}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["ticker"] == "ACME"
    assert body["is_active"] is True


def test_create_threshold_alert_without_a_threshold_is_rejected(db_client):
    headers = _auth_headers(db_client)
    response = db_client.post("/api/v1/alerts", json={"ticker": "ACME", "condition_type": "PRICE_ABOVE"}, headers=headers)
    assert response.status_code == 400


def test_duplicate_alert_returns_409(db_client):
    headers = _auth_headers(db_client)
    payload = {"ticker": "ACME", "condition_type": "PRICE_ABOVE", "threshold_value": "100"}
    db_client.post("/api/v1/alerts", json=payload, headers=headers)
    response = db_client.post("/api/v1/alerts", json=payload, headers=headers)
    assert response.status_code == 409


def test_deleting_someone_elses_alert_returns_404(db_client):
    alice_headers = _auth_headers(db_client, email="alice@example.com")
    bob_headers = _auth_headers(db_client, email="bob@example.com")
    alert = db_client.post(
        "/api/v1/alerts", json={"ticker": "ACME", "condition_type": "PRICE_ABOVE", "threshold_value": "100"}, headers=alice_headers
    ).json()

    response = db_client.delete(f"/api/v1/alerts/{alert['id']}", headers=bob_headers)
    assert response.status_code == 404

    assert db_client.get("/api/v1/alerts", headers=alice_headers).json() != []
    response = db_client.delete(f"/api/v1/alerts/{alert['id']}", headers=alice_headers)
    assert response.status_code == 204


def test_toggle_alert_active(db_client):
    headers = _auth_headers(db_client)
    alert = db_client.post(
        "/api/v1/alerts", json={"ticker": "ACME", "condition_type": "PRICE_ABOVE", "threshold_value": "100"}, headers=headers
    ).json()

    response = db_client.patch(f"/api/v1/alerts/{alert['id']}", json={"is_active": False}, headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_evaluate_reports_met_and_records_a_trigger(db_client):
    headers = _auth_headers(db_client)
    db_client.post("/api/v1/alerts", json={"ticker": "ACME", "condition_type": "PRICE_ABOVE", "threshold_value": "100"}, headers=headers)

    _override_market({"ACME": _quote_result("ACME", "150")})
    try:
        response = db_client.post("/api/v1/alerts/evaluate", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["evaluations"][0]["status"] == "met"
        assert body["evaluations"][0]["newly_triggered"] is True

        triggers = db_client.get("/api/v1/alerts/triggers", headers=headers).json()
        assert len(triggers) == 1
        assert triggers[0]["acknowledged"] is False

        ack = db_client.post(f"/api/v1/alerts/triggers/{triggers[0]['id']}/acknowledge", headers=headers)
        assert ack.status_code == 204
        unacknowledged = db_client.get("/api/v1/alerts/triggers?unacknowledged_only=true", headers=headers).json()
        assert unacknowledged == []
    finally:
        _clear_market_override()


def test_evaluate_never_touches_another_users_alerts(db_client):
    alice_headers = _auth_headers(db_client, email="alice@example.com")
    bob_headers = _auth_headers(db_client, email="bob@example.com")
    db_client.post("/api/v1/alerts", json={"ticker": "ACME", "condition_type": "PRICE_ABOVE", "threshold_value": "100"}, headers=alice_headers)

    response = db_client.post("/api/v1/alerts/evaluate", headers=bob_headers)
    assert response.status_code == 200
    assert response.json()["evaluations"] == []
