"""A ticker found via the fast local search list never goes through
`/company-search`'s auto-register path, so it would otherwise stay
permanently unmapped and Screener's historical close/DMA series (its
"primary" historical source) would silently never activate for it --
even though Screener genuinely has the data. `ScreenerHistoricalProvider`
now resolves and registers the mapping itself, lazily, on first use.
See `app/sources/historical.py::ScreenerHistoricalProvider._resolve_and_register_mapping`.
"""

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.data.providers.screener_client import ScreenerClient
from app.db.base import Base
from app.db.models import ScreenerCompanyMappingRow
from app.sources.historical import ScreenerHistoricalProvider
from app.sources.identity import CompanyIdentity
from app.sources.provenance import SourceStatus

BASE_URL = "http://test-screener:9999"
SEARCH_PATH = f"{BASE_URL}/api/company/search/"


def _chart_path(company_id: int) -> str:
    return f"{BASE_URL}/api/company/{company_id}/chart/"


_CHART_RAW = {
    "datasets": [
        {"metric": "Price", "values": [["2026-09-02", "178.35"], ["2026-09-03", "181.07"]]},
        {"metric": "DMA50", "values": [["2026-09-03", "194.04"]]},
        {"metric": "DMA200", "values": [["2026-09-03", "202.90"]]},
        {"metric": "Volume", "values": [["2026-09-03", 5698964, {"delivery": None}]]},
    ]
}

_SEARCH_RESULTS = [
    {"id": 2726, "name": "Reliance Industries Ltd", "url": "/company/RELIANCE/consolidated/"},
    {"id": 2729, "name": "Reliance Power Ltd", "url": "/company/RPOWER/consolidated/"},
]


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def _client() -> ScreenerClient:
    return ScreenerClient(base_url=BASE_URL, session_cookie="test-cookie")


def _identity(ticker: str = "RELIANCE", screener_company_id: int | None = None) -> CompanyIdentity:
    return CompanyIdentity(canonical_ticker=ticker, screener_company_id=screener_company_id)


@respx.mock
async def test_resolves_and_registers_a_mapping_on_first_use(db_session):
    respx.get(SEARCH_PATH).mock(return_value=httpx.Response(200, json=_SEARCH_RESULTS))
    respx.get(_chart_path(2726)).mock(return_value=httpx.Response(200, json=_CHART_RAW))

    provider = ScreenerHistoricalProvider(_client())
    points, attempt = await provider.get_recent_prices(db_session, _identity(screener_company_id=None), limit=30)

    assert attempt.status == SourceStatus.SUCCESS
    assert len(points) == 2

    row = await db_session.get(ScreenerCompanyMappingRow, "RELIANCE")
    assert row is not None
    assert row.screener_company_id == 2726


@respx.mock
async def test_never_registers_an_unrelated_company_when_no_exact_match(db_session):
    respx.get(SEARCH_PATH).mock(
        return_value=httpx.Response(
            200, json=[{"id": 999, "name": "Something Else Ltd", "url": "/company/SOMETHINGELSE/consolidated/"}]
        )
    )

    provider = ScreenerHistoricalProvider(_client())
    points, attempt = await provider.get_recent_prices(db_session, _identity("NOTFOUND"), limit=30)

    assert points == []
    assert attempt.status == SourceStatus.UNAVAILABLE
    assert (await db_session.execute(select(ScreenerCompanyMappingRow))).scalars().all() == []


@respx.mock
async def test_search_failure_degrades_to_unavailable_without_raising(db_session):
    respx.get(SEARCH_PATH).mock(return_value=httpx.Response(500))

    provider = ScreenerHistoricalProvider(_client())
    points, attempt = await provider.get_recent_prices(db_session, _identity(), limit=30)

    assert points == []
    assert attempt.status == SourceStatus.UNAVAILABLE


@respx.mock
async def test_an_already_mapped_ticker_never_triggers_a_search_call(db_session):
    search_route = respx.get(SEARCH_PATH).mock(return_value=httpx.Response(200, json=_SEARCH_RESULTS))
    respx.get(_chart_path(2726)).mock(return_value=httpx.Response(200, json=_CHART_RAW))

    provider = ScreenerHistoricalProvider(_client())
    _, attempt = await provider.get_recent_prices(db_session, _identity(screener_company_id=2726), limit=30)

    assert attempt.status == SourceStatus.SUCCESS
    assert search_route.call_count == 0


@respx.mock
async def test_no_cookie_never_attempts_a_lazy_search(db_session):
    search_route = respx.get(SEARCH_PATH).mock(return_value=httpx.Response(200, json=_SEARCH_RESULTS))

    provider = ScreenerHistoricalProvider(ScreenerClient(base_url=BASE_URL))
    points, attempt = await provider.get_recent_prices(db_session, _identity(screener_company_id=None), limit=30)

    assert points == []
    assert attempt.status == SourceStatus.NOT_CONFIGURED
    assert search_route.call_count == 0


@respx.mock
async def test_updates_an_existing_mapping_row_instead_of_duplicating_it(db_session):
    db_session.add(
        ScreenerCompanyMappingRow(ticker="RELIANCE", company_name="Old Name", screener_company_id=1, consolidated=True)
    )
    await db_session.commit()

    respx.get(SEARCH_PATH).mock(return_value=httpx.Response(200, json=_SEARCH_RESULTS))
    respx.get(_chart_path(2726)).mock(return_value=httpx.Response(200, json=_CHART_RAW))

    provider = ScreenerHistoricalProvider(_client())
    # No id on the identity -- forces the lazy path even though a stale
    # mapping already exists in the DB (simulates the resolver's own
    # in-memory identity not having been refreshed mid-run).
    await provider.get_recent_prices(db_session, _identity(screener_company_id=None), limit=30)

    rows = (await db_session.execute(select(ScreenerCompanyMappingRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].screener_company_id == 2726
    assert rows[0].company_name == "Reliance Industries Ltd"
