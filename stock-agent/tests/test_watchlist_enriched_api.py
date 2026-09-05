"""`GET /api/v1/watchlist/enriched` -- watchlist items plus a live quote
and the latest research score, without duplicating `get_summary`'s
quote logic or `/research/recent`'s score logic (see
`app/portfolio/service.py::list_watchlist_enriched`)."""

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.portfolio import get_portfolio_service
from app.db.base import Base, get_db
from app.db.models import ResearchAnalysisSnapshotRow, ResearchRunRow
from app.main import app
from app.models.market import (
    MarketDataError,
    MarketDataErrorCode,
    MarketQuote,
    MarketSnapshot,
    MarketSnapshotResult,
    MarketStatus,
    PriceFreshness,
)
from app.portfolio.service import PortfolioService

ENDPOINT = "/api/v1/watchlist/enriched"


class _StubMarketDataService:
    def __init__(self, results: dict) -> None:
        self._results = results

    async def get_quote(self, ticker: str) -> MarketSnapshotResult:
        return self._results.get(
            ticker,
            MarketSnapshotResult(
                status="error",
                error=MarketDataError(code=MarketDataErrorCode.TICKER_NOT_FOUND, message="not found"),
            ),
        )


def _quote_result(ticker: str, price: str, change_percent: str = "1.5") -> MarketSnapshotResult:
    quote = MarketQuote(
        ticker=ticker, current_price=Decimal(price), previous_close=Decimal(price),
        change=Decimal(0), change_percent=Decimal(change_percent), currency="USD",
        market_status=MarketStatus.OPEN, market_timestamp=None,
        data_timestamp="2026-08-21T00:00:00+00:00", freshness=PriceFreshness.LIVE, source="stub",
    )
    snapshot = MarketSnapshot(ticker=ticker, quote=quote, recent_prices=[], fetched_at="2026-08-21T00:00:00+00:00")
    return MarketSnapshotResult(status="success", snapshot=snapshot)


@pytest.fixture
async def seeded_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), session_factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_portfolio_service, None)
        await engine.dispose()


async def _seed_score(
    session_factory, *, ticker: str, overall_score: str = "78", band: str = "good",
    completed_at: datetime = datetime(2026, 9, 1, tzinfo=timezone.utc),
) -> None:
    async with session_factory() as db:
        run = ResearchRunRow(
            ticker=ticker, research_date=completed_at.date(),
            started_at=completed_at,
            completed_at=completed_at,
            status="COMPLETED", run_type="NORMAL",
            data_version="v1", calculation_version="v1", forecast_version="v1",
            prompt_version="v1", model_version="test",
        )
        db.add(run)
        await db.flush()
        db.add(
            ResearchAnalysisSnapshotRow(
                research_run_id=run.id, ticker=ticker, analysis_version="v1",
                financial_analysis_json="{}", valuation_json=None,
                scoring_json=json.dumps({"company_name": "Test Co", "overall_score": overall_score, "band": band}),
            )
        )
        await db.commit()


def _signup(client, email="alice@example.com") -> dict:
    token = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _override_market(results: dict) -> None:
    app.dependency_overrides[get_portfolio_service] = lambda: PortfolioService(_StubMarketDataService(results))


@pytest.mark.asyncio
async def test_requires_authentication(seeded_client):
    client, _ = seeded_client
    assert client.get(ENDPOINT).status_code == 401


@pytest.mark.asyncio
async def test_empty_watchlist_returns_empty_list(seeded_client):
    client, _ = seeded_client
    headers = _signup(client)
    assert client.get(ENDPOINT, headers=headers).json() == []


@pytest.mark.asyncio
async def test_combines_watchlist_membership_quote_and_score(seeded_client):
    client, session_factory = seeded_client
    headers = _signup(client)
    client.post("/api/v1/watchlist", json={"ticker": "HUDCO"}, headers=headers)
    _override_market({"HUDCO": _quote_result("HUDCO", "100.50")})
    await _seed_score(session_factory, ticker="HUDCO", overall_score="81", band="strong")

    entry = client.get(ENDPOINT, headers=headers).json()[0]

    assert entry["ticker"] == "HUDCO"
    assert entry["current_price"] == "100.50"
    assert entry["price_status"] == "live"
    assert entry["overall_score"] == "81"
    assert entry["band"] == "strong"
    assert entry["last_researched_at"] is not None


@pytest.mark.asyncio
async def test_watchlisted_but_never_researched_ticker_has_null_score_not_a_fabricated_one(seeded_client):
    client, _ = seeded_client
    headers = _signup(client)
    client.post("/api/v1/watchlist", json={"ticker": "NEWCO"}, headers=headers)
    _override_market({"NEWCO": _quote_result("NEWCO", "50")})

    entry = client.get(ENDPOINT, headers=headers).json()[0]

    assert entry["current_price"] == "50"
    assert entry["overall_score"] is None
    assert entry["band"] is None
    assert entry["last_researched_at"] is None


@pytest.mark.asyncio
async def test_unavailable_quote_never_becomes_a_fabricated_price(seeded_client):
    client, _ = seeded_client
    headers = _signup(client)
    client.post("/api/v1/watchlist", json={"ticker": "GHOST"}, headers=headers)
    _override_market({})  # unknown ticker -> the stub's default error result

    entry = client.get(ENDPOINT, headers=headers).json()[0]

    assert entry["current_price"] is None
    assert entry["price_status"] == "unavailable"


@pytest.mark.asyncio
async def test_only_the_latest_score_is_used_when_a_ticker_has_multiple_runs(seeded_client):
    client, session_factory = seeded_client
    headers = _signup(client)
    client.post("/api/v1/watchlist", json={"ticker": "TCS"}, headers=headers)
    _override_market({"TCS": _quote_result("TCS", "3500")})
    await _seed_score(
        session_factory, ticker="TCS", overall_score="60", band="fair",
        completed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    await _seed_score(
        session_factory, ticker="TCS", overall_score="90", band="excellent",
        completed_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )

    entry = client.get(ENDPOINT, headers=headers).json()[0]
    assert entry["overall_score"] == "90"


@pytest.mark.asyncio
async def test_does_not_leak_another_users_watchlist(seeded_client):
    client, session_factory = seeded_client
    headers_a = _signup(client, email="a@example.com")
    headers_b = _signup(client, email="b@example.com")
    client.post("/api/v1/watchlist", json={"ticker": "TSLA"}, headers=headers_a)
    _override_market({"TSLA": _quote_result("TSLA", "200")})

    assert client.get(ENDPOINT, headers=headers_b).json() == []
