"""`GET /api/v1/research/recent` -- the cross-ticker "latest research per
ticker" listing that backs the Intelligence home page and `/research`
history page without an N+1 fan-out (see `app/api/research.py`)."""

import json
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.db.models import ResearchAnalysisSnapshotRow, ResearchRunRow
from app.main import app

ENDPOINT = "/api/v1/research/recent"


@pytest.fixture
async def seeded_client():
    """Own in-memory SQLite engine (not the shared `db_dependency_override`
    fixture) so this test can seed rows directly through the same
    session factory the app's `get_db` override yields from."""
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
        await engine.dispose()


async def _seed_run(
    session_factory,
    *,
    ticker: str,
    completed_at: datetime,
    status: str = "COMPLETED",
    company_name: str = "Test Co",
    overall_score: str | None = "78",
    band: str | None = "good",
) -> str:
    async with session_factory() as db:  # type: AsyncSession
        run = ResearchRunRow(
            ticker=ticker,
            research_date=completed_at.date(),
            started_at=completed_at,
            completed_at=completed_at,
            status=status,
            run_type="NORMAL",
            data_version="v1", calculation_version="v1", forecast_version="v1",
            prompt_version="v1", model_version="test",
        )
        db.add(run)
        await db.flush()
        db.add(
            ResearchAnalysisSnapshotRow(
                research_run_id=run.id,
                ticker=ticker,
                analysis_version="v1",
                financial_analysis_json="{}",
                valuation_json=None,
                scoring_json=json.dumps(
                    {"company_name": company_name, "overall_score": overall_score, "band": band}
                ),
            )
        )
        await db.commit()
        return run.id


@pytest.mark.asyncio
async def test_returns_only_the_latest_run_per_ticker(seeded_client):
    client, session_factory = seeded_client
    await _seed_run(session_factory, ticker="HUDCO", completed_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    latest_id = await _seed_run(session_factory, ticker="HUDCO", completed_at=datetime(2026, 9, 3, tzinfo=timezone.utc))
    await _seed_run(session_factory, ticker="TCS", completed_at=datetime(2026, 9, 2, tzinfo=timezone.utc))

    response = client.get(ENDPOINT)
    assert response.status_code == 200
    body = response.json()

    by_ticker = {entry["ticker"]: entry for entry in body}
    assert set(by_ticker) == {"HUDCO", "TCS"}
    assert by_ticker["HUDCO"]["research_run_id"] == latest_id


@pytest.mark.asyncio
async def test_ordered_newest_first_across_tickers(seeded_client):
    client, session_factory = seeded_client
    await _seed_run(session_factory, ticker="A", completed_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    await _seed_run(session_factory, ticker="B", completed_at=datetime(2026, 9, 3, tzinfo=timezone.utc))
    await _seed_run(session_factory, ticker="C", completed_at=datetime(2026, 9, 2, tzinfo=timezone.utc))

    body = client.get(ENDPOINT).json()
    assert [entry["ticker"] for entry in body] == ["B", "C", "A"]


@pytest.mark.asyncio
async def test_includes_company_name_and_score_from_the_analysis_snapshot(seeded_client):
    client, session_factory = seeded_client
    await _seed_run(
        session_factory, ticker="HUDCO", completed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        company_name="Housing & Urban Development Corp", overall_score="81.5", band="strong",
    )

    entry = client.get(ENDPOINT).json()[0]
    assert entry["company_name"] == "Housing & Urban Development Corp"
    assert entry["overall_score"] == "81.5"
    assert entry["band"] == "strong"


@pytest.mark.asyncio
async def test_excludes_failed_and_running_runs(seeded_client):
    client, session_factory = seeded_client
    await _seed_run(session_factory, ticker="FAIL", completed_at=datetime(2026, 9, 1, tzinfo=timezone.utc), status="FAILED")

    body = client.get(ENDPOINT).json()
    assert body == []


@pytest.mark.asyncio
async def test_partial_runs_are_included(seeded_client):
    client, session_factory = seeded_client
    await _seed_run(session_factory, ticker="PARTIAL", completed_at=datetime(2026, 9, 1, tzinfo=timezone.utc), status="PARTIAL")

    body = client.get(ENDPOINT).json()
    assert len(body) == 1
    assert body[0]["status"] == "PARTIAL"


@pytest.mark.asyncio
async def test_empty_when_nothing_researched_yet(seeded_client):
    client, _ = seeded_client
    response = client.get(ENDPOINT)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_recent_is_never_matched_as_a_ticker_by_the_catch_all_route(seeded_client):
    """Regression guard for route-declaration order: `/recent` must be
    registered before `GET /{ticker}`, or this request would 404 as
    "no research found for RECENT"."""
    client, _ = seeded_client
    response = client.get(ENDPOINT)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_respects_limit_and_offset(seeded_client):
    client, session_factory = seeded_client
    for i, ticker in enumerate(["A", "B", "C"]):
        await _seed_run(session_factory, ticker=ticker, completed_at=datetime(2026, 9, 1 + i, tzinfo=timezone.utc))

    first_page = client.get(ENDPOINT, params={"limit": 2}).json()
    assert [e["ticker"] for e in first_page] == ["C", "B"]

    second_page = client.get(ENDPOINT, params={"limit": 2, "offset": 2}).json()
    assert [e["ticker"] for e in second_page] == ["A"]
