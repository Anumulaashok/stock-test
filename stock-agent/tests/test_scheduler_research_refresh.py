"""`app.scheduler.research_refresh` -- the twice-daily job that forces a
recompute for every previously-researched ticker (see the module
docstring for why: a NORMAL request reuses today's snapshot all day,
so nothing else keeps financial analysis/valuation/scoring/forecast
current without an active trigger)."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.scheduler.research_refresh as refresh_module
from app.core.config import Settings
from app.db.base import Base
from app.db.models import ResearchRunRow
from app.models.research_run import ResearchRunRequest, ResearchRunResult, ResearchRunStatus, ResearchRunType
from app.snapshot.exceptions import ResearchInProgressError


def _settings(**overrides) -> Settings:
    defaults = dict(
        llm_provider="local", local_llm_base_url="http://test-llm:8080/v1", local_llm_model="test-model",
        financial_data_provider="fmp", fmp_api_key="test-key",
        database_url="postgresql+psycopg://user:pass@localhost/db",
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed_run(session_factory, *, ticker: str, status: str = "COMPLETED", research_date: date | None = None) -> None:
    research_date = research_date or date.today()
    async with session_factory() as db:
        db.add(
            ResearchRunRow(
                ticker=ticker, research_date=research_date, started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc), status=status, run_type="NORMAL",
                data_version="v1", calculation_version="v1", forecast_version="v1",
                prompt_version="v1", model_version="test",
            )
        )
        await db.commit()


class _StubService:
    def __init__(self, *, fail_tickers: set[str] | None = None, in_progress_tickers: set[str] | None = None) -> None:
        self.calls: list[ResearchRunRequest] = []
        self._fail = fail_tickers or set()
        self._in_progress = in_progress_tickers or set()

    async def run_research(self, db, request: ResearchRunRequest) -> ResearchRunResult:
        self.calls.append(request)
        if request.ticker in self._in_progress:
            raise ResearchInProgressError(f"{request.ticker} already running")
        if request.ticker in self._fail:
            raise RuntimeError("provider exploded")
        return ResearchRunResult(
            research_run_id="run-x", ticker=request.ticker, research_date=date.today(),
            run_type=ResearchRunType.FORCE_REFRESH, status=ResearchRunStatus.COMPLETED, is_new_run=True,
            started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
            result={"company": {"name": request.ticker, "ticker": request.ticker}, "status": "calculated", "warnings": []},
        )


def _patch_service(monkeypatch, service: _StubService) -> None:
    monkeypatch.setattr(refresh_module, "build_research_snapshot_service", lambda settings, db: service)


@pytest.fixture(autouse=True)
def _allow_financial_provider(monkeypatch):
    """`get_financial_data_provider` needs a real registered provider
    factory to not raise -- stub it to a no-op success so these tests
    exercise only the refresh-job logic, not provider wiring."""
    monkeypatch.setattr(refresh_module, "get_financial_data_provider", lambda settings: object())


async def test_refreshes_every_ticker_with_a_completed_or_partial_run(session_factory, monkeypatch):
    await _seed_run(session_factory, ticker="A", status="COMPLETED")
    await _seed_run(session_factory, ticker="B", status="PARTIAL")
    await _seed_run(session_factory, ticker="C", status="FAILED")
    await _seed_run(session_factory, ticker="D", status="RUNNING")

    service = _StubService()
    _patch_service(monkeypatch, service)

    await refresh_module.refresh_all_researched_tickers(session_factory, _settings())

    refreshed = {c.ticker for c in service.calls}
    assert refreshed == {"A", "B"}
    assert all(c.force_refresh for c in service.calls)


async def test_excludes_tickers_last_researched_before_the_stale_cutoff(session_factory, monkeypatch):
    old_date = date.today() - timedelta(days=refresh_module._STALE_CUTOFF_DAYS + 5)
    await _seed_run(session_factory, ticker="STALE", status="COMPLETED", research_date=old_date)
    await _seed_run(session_factory, ticker="FRESH", status="COMPLETED")

    service = _StubService()
    _patch_service(monkeypatch, service)

    await refresh_module.refresh_all_researched_tickers(session_factory, _settings())

    assert {c.ticker for c in service.calls} == {"FRESH"}


async def test_one_tickers_failure_never_blocks_the_rest_of_the_batch(session_factory, monkeypatch):
    await _seed_run(session_factory, ticker="GOOD")
    await _seed_run(session_factory, ticker="BAD")

    service = _StubService(fail_tickers={"BAD"})
    _patch_service(monkeypatch, service)

    await refresh_module.refresh_all_researched_tickers(session_factory, _settings())

    assert {c.ticker for c in service.calls} == {"GOOD", "BAD"}  # both attempted


async def test_research_in_progress_is_skipped_not_raised(session_factory, monkeypatch):
    await _seed_run(session_factory, ticker="BUSY")

    service = _StubService(in_progress_tickers={"BUSY"})
    _patch_service(monkeypatch, service)

    # Must not raise.
    await refresh_module.refresh_all_researched_tickers(session_factory, _settings())
    assert {c.ticker for c in service.calls} == {"BUSY"}


async def test_no_tickers_ever_researched_does_nothing(session_factory, monkeypatch):
    service = _StubService()
    _patch_service(monkeypatch, service)

    await refresh_module.refresh_all_researched_tickers(session_factory, _settings())
    assert service.calls == []


async def test_skips_entirely_when_the_financial_provider_is_unconfigured(session_factory, monkeypatch):
    await _seed_run(session_factory, ticker="A")

    def _raise(settings):
        raise ValueError("not configured")

    monkeypatch.setattr(refresh_module, "get_financial_data_provider", _raise)

    service = _StubService()
    _patch_service(monkeypatch, service)

    await refresh_module.refresh_all_researched_tickers(session_factory, _settings())
    assert service.calls == []


async def test_duplicate_ticker_across_multiple_runs_is_only_refreshed_once(session_factory, monkeypatch):
    await _seed_run(session_factory, ticker="A", research_date=date.today())
    await _seed_run(session_factory, ticker="A", research_date=date.today() - timedelta(days=1))

    service = _StubService()
    _patch_service(monkeypatch, service)

    await refresh_module.refresh_all_researched_tickers(session_factory, _settings())
    assert [c.ticker for c in service.calls] == ["A"]
