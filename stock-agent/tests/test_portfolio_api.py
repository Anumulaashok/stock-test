from decimal import Decimal

from app.api.portfolio import get_portfolio_service
from app.core.config import get_settings
from app.main import app
from app.models.market import MarketDataError, MarketDataErrorCode, MarketQuote, MarketSnapshot, MarketSnapshotResult, MarketStatus, PriceFreshness
from app.portfolio.service import PortfolioService


def _signup(db_client, email="alice@example.com", password="correct-horse"):
    return db_client.post("/api/v1/auth/signup", json={"email": email, "password": password})


def _auth_headers(db_client, email="alice@example.com") -> dict:
    token = _signup(db_client, email=email).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class _StubMarketDataService:
    """A minimal `MarketDataService` stand-in whose `.get_quote()` returns
    a preset result per ticker, so summary calculations can be tested
    without any real provider or HTTP mocking."""

    def __init__(self, results: dict[str, MarketSnapshotResult]) -> None:
        self._results = results

    async def get_quote(self, ticker: str) -> MarketSnapshotResult:
        return self._results.get(
            ticker,
            MarketSnapshotResult(
                status="error",
                error=MarketDataError(code=MarketDataErrorCode.TICKER_NOT_FOUND, message="not found"),
            ),
        )


def _quote_result(ticker: str, price: str, freshness: PriceFreshness = PriceFreshness.LIVE) -> MarketSnapshotResult:
    quote = MarketQuote(
        ticker=ticker,
        current_price=Decimal(price),
        previous_close=Decimal(price),
        change=Decimal(0),
        change_percent=Decimal(0),
        currency="USD",
        market_status=MarketStatus.OPEN,
        market_timestamp=None,
        data_timestamp="2026-08-21T00:00:00+00:00",
        freshness=freshness,
        source="stub",
    )
    snapshot = MarketSnapshot(ticker=ticker, quote=quote, recent_prices=[], fetched_at="2026-08-21T00:00:00+00:00")
    return MarketSnapshotResult(status="success", snapshot=snapshot)


def _override_market(results: dict[str, MarketSnapshotResult]):
    app.dependency_overrides[get_portfolio_service] = lambda: PortfolioService(
        _StubMarketDataService(results)
    )


def _clear_market_override():
    app.dependency_overrides.pop(get_portfolio_service, None)


# --- Authentication / authorization --------------------------------------------


def test_portfolio_requires_authentication(db_client):
    assert db_client.get("/api/v1/portfolio").status_code == 401
    assert db_client.get("/api/v1/portfolio/summary").status_code == 401
    assert db_client.get("/api/v1/watchlist").status_code == 401
    assert (
        db_client.post("/api/v1/portfolio/holdings", json={"ticker": "AAPL", "quantity": "1", "average_cost": "1"}).status_code
        == 401
    )


def test_holdings_start_empty(db_client):
    headers = _auth_headers(db_client)
    response = db_client.get("/api/v1/portfolio", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_add_holding_returns_created_holding(db_client):
    headers = _auth_headers(db_client)
    response = db_client.post(
        "/api/v1/portfolio/holdings",
        json={"ticker": "aapl", "quantity": "10", "average_cost": "150.00"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert Decimal(body["quantity"]) == Decimal("10")
    assert Decimal(body["average_cost"]) == Decimal("150.00")


def test_add_duplicate_holding_is_rejected(db_client):
    headers = _auth_headers(db_client)
    db_client.post(
        "/api/v1/portfolio/holdings",
        json={"ticker": "AAPL", "quantity": "10", "average_cost": "150"},
        headers=headers,
    )
    response = db_client.post(
        "/api/v1/portfolio/holdings",
        json={"ticker": "AAPL", "quantity": "5", "average_cost": "140"},
        headers=headers,
    )
    assert response.status_code == 409


def test_update_holding(db_client):
    headers = _auth_headers(db_client)
    holding = db_client.post(
        "/api/v1/portfolio/holdings",
        json={"ticker": "AAPL", "quantity": "10", "average_cost": "150"},
        headers=headers,
    ).json()

    response = db_client.patch(
        f"/api/v1/portfolio/holdings/{holding['id']}", json={"quantity": "20"}, headers=headers
    )
    assert response.status_code == 200
    assert Decimal(response.json()["quantity"]) == Decimal("20")
    assert Decimal(response.json()["average_cost"]) == Decimal("150")


def test_delete_holding(db_client):
    headers = _auth_headers(db_client)
    holding = db_client.post(
        "/api/v1/portfolio/holdings",
        json={"ticker": "AAPL", "quantity": "10", "average_cost": "150"},
        headers=headers,
    ).json()

    delete_response = db_client.delete(f"/api/v1/portfolio/holdings/{holding['id']}", headers=headers)
    assert delete_response.status_code == 204

    list_response = db_client.get("/api/v1/portfolio", headers=headers)
    assert list_response.json() == []


def test_update_nonexistent_holding_returns_404(db_client):
    headers = _auth_headers(db_client)
    response = db_client.patch(
        "/api/v1/portfolio/holdings/does-not-exist", json={"quantity": "1"}, headers=headers
    )
    assert response.status_code == 404


# --- Cross-user isolation --------------------------------------------------------


def test_user_cannot_read_another_users_holdings(db_client):
    headers_a = _auth_headers(db_client, email="alice@example.com")
    headers_b = _auth_headers(db_client, email="bob@example.com")

    db_client.post(
        "/api/v1/portfolio/holdings",
        json={"ticker": "AAPL", "quantity": "10", "average_cost": "150"},
        headers=headers_a,
    )

    response_b = db_client.get("/api/v1/portfolio", headers=headers_b)
    assert response_b.status_code == 200
    assert response_b.json() == []


def test_user_cannot_modify_another_users_holding(db_client):
    headers_a = _auth_headers(db_client, email="alice@example.com")
    headers_b = _auth_headers(db_client, email="bob@example.com")

    holding = db_client.post(
        "/api/v1/portfolio/holdings",
        json={"ticker": "AAPL", "quantity": "10", "average_cost": "150"},
        headers=headers_a,
    ).json()

    update_response = db_client.patch(
        f"/api/v1/portfolio/holdings/{holding['id']}", json={"quantity": "999"}, headers=headers_b
    )
    assert update_response.status_code == 404

    delete_response = db_client.delete(f"/api/v1/portfolio/holdings/{holding['id']}", headers=headers_b)
    assert delete_response.status_code == 404

    # Alice's holding is untouched.
    unaffected = db_client.get("/api/v1/portfolio", headers=headers_a).json()
    assert Decimal(unaffected[0]["quantity"]) == Decimal("10")


def test_user_cannot_see_another_users_watchlist(db_client):
    headers_a = _auth_headers(db_client, email="alice@example.com")
    headers_b = _auth_headers(db_client, email="bob@example.com")

    db_client.post("/api/v1/watchlist", json={"ticker": "TSLA"}, headers=headers_a)

    response_b = db_client.get("/api/v1/watchlist", headers=headers_b)
    assert response_b.status_code == 200
    assert response_b.json() == []


# --- Watchlist --------------------------------------------------------------------


def test_watchlist_add_list_delete(db_client):
    headers = _auth_headers(db_client)

    add_response = db_client.post("/api/v1/watchlist", json={"ticker": "msft"}, headers=headers)
    assert add_response.status_code == 201
    assert add_response.json()["ticker"] == "MSFT"

    list_response = db_client.get("/api/v1/watchlist", headers=headers)
    assert [item["ticker"] for item in list_response.json()] == ["MSFT"]

    delete_response = db_client.delete("/api/v1/watchlist/MSFT", headers=headers)
    assert delete_response.status_code == 204
    assert db_client.get("/api/v1/watchlist", headers=headers).json() == []


def test_watchlist_duplicate_is_rejected(db_client):
    headers = _auth_headers(db_client)
    db_client.post("/api/v1/watchlist", json={"ticker": "MSFT"}, headers=headers)
    response = db_client.post("/api/v1/watchlist", json={"ticker": "MSFT"}, headers=headers)
    assert response.status_code == 409


def test_delete_nonexistent_watchlist_item_returns_404(db_client):
    headers = _auth_headers(db_client)
    response = db_client.delete("/api/v1/watchlist/GOOG", headers=headers)
    assert response.status_code == 404


# --- Summary / market-value calculations -----------------------------------------


def test_summary_with_no_market_provider_reports_unavailable_prices(db_client, monkeypatch):
    # Explicitly disable the market data provider rather than relying on
    # FMP_API_KEY being absent from the ambient environment -- it may well
    # be configured for real (Step 4 uses it), and this test must never
    # depend on that, let alone make a live call to the real FMP API.
    monkeypatch.setenv("FMP_API_KEY", "")
    get_settings.cache_clear()

    headers = _auth_headers(db_client)
    db_client.post(
        "/api/v1/portfolio/holdings",
        json={"ticker": "AAPL", "quantity": "10", "average_cost": "150"},
        headers=headers,
    )

    response = db_client.get("/api/v1/portfolio/summary", headers=headers)
    get_settings.cache_clear()
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["invested_capital"]) == Decimal("1500")
    assert body["portfolio_value"] is None
    assert body["unrealized_gain"] is None
    assert body["holdings"][0]["current_price"] is None
    assert body["holdings"][0]["price_status"] == "unavailable"
    assert any("AAPL" in w for w in body["warnings"])


def test_summary_calculates_market_value_and_gain_from_live_quote(db_client):
    headers = _auth_headers(db_client)
    db_client.post(
        "/api/v1/portfolio/holdings",
        json={"ticker": "AAPL", "quantity": "10", "average_cost": "150"},
        headers=headers,
    )

    _override_market({"AAPL": _quote_result("AAPL", "180.00")})
    try:
        response = db_client.get("/api/v1/portfolio/summary", headers=headers)
    finally:
        _clear_market_override()

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["invested_capital"]) == Decimal("1500")
    assert Decimal(body["portfolio_value"]) == Decimal("1800.00")
    assert Decimal(body["unrealized_gain"]) == Decimal("300.00")
    assert Decimal(body["unrealized_gain_percent"]) == Decimal("20")

    holding = body["holdings"][0]
    assert Decimal(holding["current_price"]) == Decimal("180.00")
    assert holding["price_status"] == "live"
    assert Decimal(holding["market_value"]) == Decimal("1800.00")
    assert Decimal(holding["unrealized_gain"]) == Decimal("300.00")


def test_summary_partial_pricing_does_not_fabricate_total(db_client):
    headers = _auth_headers(db_client)
    db_client.post(
        "/api/v1/portfolio/holdings",
        json={"ticker": "AAPL", "quantity": "10", "average_cost": "150"},
        headers=headers,
    )
    db_client.post(
        "/api/v1/portfolio/holdings",
        json={"ticker": "UNKNOWN", "quantity": "5", "average_cost": "10"},
        headers=headers,
    )

    _override_market({"AAPL": _quote_result("AAPL", "180.00")})
    try:
        response = db_client.get("/api/v1/portfolio/summary", headers=headers)
    finally:
        _clear_market_override()

    body = response.json()
    # UNKNOWN has no quote -> the aggregate must not silently treat it as
    # $0; the total is None (not a fabricated partial number treated as
    # complete), while the per-holding data still shows what IS known.
    assert body["unrealized_gain"] is None
    assert body["unrealized_gain_percent"] is None
    priced = {h["ticker"]: h for h in body["holdings"]}
    assert Decimal(priced["AAPL"]["market_value"]) == Decimal("1800.00")
    assert priced["UNKNOWN"]["market_value"] is None
