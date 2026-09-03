"""Service-level tests for `ResearchSnapshotService` (Phase 1-9, 12, 19
of the persistent research-snapshot feature).

Uses real deterministic services (financial/valuation/scoring/forecast
-- all pure Python, no network) wired to a real in-memory SQLite
database, with fakes only for the two things that would otherwise touch
the network: the financial-data fetch and the LLM analyst call. This
lets tests assert call counts directly, which is the only reliable way
to prove "no unnecessary provider/LLM call" rather than just checking
the returned payload looks right.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.analyst.service import AnalystService  # noqa: F401 -- documents the real type FakeAnalystService stands in for
from app.application.service import AnalysisApplicationService
from app.data.models import (
    CompanyIdentifier,
    FinancialDataError,
    FinancialDataErrorCode,
    FinancialDataFetchResult,
    FinancialDataMetadata,
    FinancialDataResult,
)
from app.db.base import Base
from app.db.models import (
    ForecastSnapshotRow,
    LLMAnalysisSnapshotRow,
    RawResearchDataRow,
    ResearchAnalysisSnapshotRow,
    ResearchReportSnapshotRow,
    ResearchRunRow,
)
from app.financial.service import FinancialAnalysisService
from app.forecasting.service import ForecastingService
from app.models.analyst import AnalystError, AnalystErrorCode, AnalystResponse, AnalystResult, AnalystSection
from app.models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFinancials,
    IncomeStatement,
)
from app.models.market import MarketQuote, MarketSnapshot, MarketSnapshotResult, PriceFreshness
from app.models.research_run import ResearchRunRequest, ResearchRunStatus, ResearchRunType
from app.pipeline.service import AnalysisPipelineService
from app.scoring.service import ScoringService
from app.snapshot.service import ResearchSnapshotService
from app.valuation.service import ValuationService


def d(value) -> Decimal:
    return Decimal(str(value))


def _company_financials() -> CompanyFinancials:
    return CompanyFinancials(
        company_name="Acme Corp",
        ticker="ACME",
        income_statements=[
            IncomeStatement(period="FY2023", revenue=d(100), net_income=d(10), eps=d(1)),
            IncomeStatement(period="FY2024", revenue=d(110), net_income=d(11), eps=d("1.1")),
            IncomeStatement(period="FY2025", revenue=d(121), net_income=d("12.1"), eps=d("1.21")),
        ],
        balance_sheets=[
            BalanceSheet(period="FY2025", total_debt=d(50), cash_and_equivalents=d(20), shareholders_equity=d(200)),
        ],
        cash_flow_statements=[
            CashFlowStatement(period="FY2023", free_cash_flow=d(40)),
            CashFlowStatement(period="FY2024", free_cash_flow=d(44)),
            CashFlowStatement(period="FY2025", free_cash_flow=d("48.4")),
        ],
    )


class FakeFinancialDataFetcher:
    """Stands in for `CachedFinancialDataService`, including its actual
    caching behavior (success cached indefinitely here -- real TTL is 7
    days -- failure never cached by this fake, though the real
    `CachedFinancialDataService` now negative-caches too, see
    `tests/test_cache_financial_data.py`). `ResearchSnapshotService` now
    fetches financial data exactly once per fresh run and reuses the
    same `FinancialDataFetchResult` for both raw-data capture and
    `AnalysisApplicationService` (request-scoped dedup) -- `calls` counts
    every invocation; `provider_fetches` counts only the ones that did
    NOT hit this fake's own cache -- the reuse tests assert on whichever
    one answers "was there unnecessary work"."""

    def __init__(self, company_financials: CompanyFinancials | None = None, succeed: bool = True):
        self._company_financials = company_financials or _company_financials()
        self._succeed = succeed
        self.calls = 0
        self.provider_fetches = 0
        self._cached: FinancialDataFetchResult | None = None

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataFetchResult:
        self.calls += 1
        if self._cached is not None:
            return self._cached

        self.provider_fetches += 1
        if not self._succeed:
            return FinancialDataFetchResult(
                status="error",
                error=FinancialDataError(code=FinancialDataErrorCode.COMPANY_NOT_FOUND, message="not found"),
            )
        result = FinancialDataFetchResult(
            status="success",
            data=FinancialDataResult(
                company_financials=self._company_financials,
                metadata=FinancialDataMetadata(
                    provider="fmp", source_identifier=identifier.ticker, retrieved_at="2026-09-02T00:00:00Z"
                ),
            ),
        )
        self._cached = result
        return result


class FakeAnalystService:
    def __init__(self, status: str = "success"):
        self._status = status
        self.calls = 0

    async def analyze(self, financial_analysis, valuation, scoring, company_financials=None, research=None) -> AnalystResult:
        self.calls += 1
        if self._status == "success":
            section = AnalystSection(text="ok")
            return AnalystResult(
                status="success",
                response=AnalystResponse(
                    company_name="Acme Corp", investment_thesis=section, profitability_analysis=section,
                    growth_analysis=section, financial_health_analysis=section, cash_flow_analysis=section,
                    valuation_analysis=section, risk_analysis=section,
                ),
            )
        return AnalystResult(status="error", error=AnalystError(code=AnalystErrorCode.LLM_UNAVAILABLE, message="down"))


class FakeMarketDataFetcher:
    """Stands in for `CachedMarketDataService` -- returns a quote whose
    `current_price` changes on every call (`self.calls`) so tests can
    prove a "fresh" quote was actually fetched rather than reused from
    the persisted report snapshot."""

    def __init__(self, base_price: int = 100):
        self._base_price = base_price
        self.calls = 0

    async def get_snapshot(self, ticker: str, include_recent_prices: bool = True) -> MarketSnapshotResult:
        self.calls += 1
        price = Decimal(self._base_price + self.calls)
        quote = MarketQuote(
            ticker=ticker,
            current_price=price,
            previous_close=price - 1,
            change=Decimal(1),
            change_percent=Decimal("1.0"),
            currency="INR",
            data_timestamp="2026-09-02T10:00:00Z",
            freshness=PriceFreshness.DELAYED,
            source="fake",
            market_cap=Decimal(1_000_000),
            year_high=price + 10,
            year_low=price - 10,
        )
        snapshot = MarketSnapshot(ticker=ticker, quote=quote, recent_prices=[], fetched_at="2026-09-02T10:00:00Z")
        return MarketSnapshotResult(status="success", snapshot=snapshot)


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


def _build_service(financial_fetcher, analyst, clock=None, market_fetcher=None) -> ResearchSnapshotService:
    pipeline = AnalysisPipelineService(
        financial_service=FinancialAnalysisService(),
        valuation_service=ValuationService(),
        scoring_service=ScoringService(),
        analyst_service=analyst,  # unused by the pipeline itself (run_analyst=False), but required
        forecasting_service=ForecastingService(),
    )
    application_service = AnalysisApplicationService(financial_fetcher, pipeline, market_data_service=market_fetcher)
    return ResearchSnapshotService(
        application_service=application_service,
        financial_data_service=financial_fetcher,
        market_data_service=market_fetcher,
        analyst_service=analyst,
        financial_data_provider_name="fmp",
        market_data_provider_name="yfinance" if market_fetcher else None,
        llm_provider_name="local",
        model_version="test-model",
        clock=clock,
    )


def _clock_at(when: datetime):
    return lambda: when


def _advancing_clock(start: datetime, step_seconds: int = 1):
    """A real clock always advances between calls -- `completed_at`
    ordering (`_find_reusable_run`'s tiebreak between same-day runs)
    depends on that. A fixed test clock would make two runs' timestamps
    identical, which is a test artifact a fixed clock would hide, not a
    real production ambiguity."""
    state = {"t": start}

    def _clock() -> datetime:
        state["t"] = state["t"] + timedelta(seconds=step_seconds)
        return state["t"]

    return _clock


NOW = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)


# --- normal research: first run does the work, second reuses it ------------------------


@pytest.mark.asyncio
async def test_first_research_run_saves_every_stage(db_session):
    fetcher = FakeFinancialDataFetcher()
    analyst = FakeAnalystService()
    service = _build_service(fetcher, analyst, clock=_clock_at(NOW))

    result = await service.run_research(db_session, ResearchRunRequest(ticker="acme"))

    assert result.is_new_run is True
    assert result.ticker == "ACME"
    assert result.status == ResearchRunStatus.COMPLETED
    assert result.result.status.value == "calculated"
    # Request-scoped dedup: raw-data capture fetches once and that same
    # FinancialDataFetchResult is reused by AnalysisApplicationService --
    # not a second call at all (not even a cache hit).
    assert fetcher.calls == 1
    assert fetcher.provider_fetches == 1
    assert analyst.calls == 1

    run_row = await db_session.get(ResearchRunRow, result.research_run_id)
    assert run_row.status == "COMPLETED"
    assert run_row.run_type == "NORMAL"
    assert run_row.data_version == "v1"
    assert run_row.calculation_version == "v1"
    assert run_row.forecast_version == "v1"
    assert run_row.prompt_version == "v1"
    assert run_row.model_version == "test-model"

    raw_rows = (
        await db_session.execute(select(RawResearchDataRow).where(RawResearchDataRow.research_run_id == run_row.id))
    ).scalars().all()
    assert any(r.data_type == "FINANCIAL_STATEMENTS" for r in raw_rows)

    analysis_row = (
        await db_session.execute(
            select(ResearchAnalysisSnapshotRow).where(ResearchAnalysisSnapshotRow.research_run_id == run_row.id)
        )
    ).scalar_one()
    assert analysis_row.financial_analysis_json is not None

    forecast_rows = (
        await db_session.execute(select(ForecastSnapshotRow).where(ForecastSnapshotRow.research_run_id == run_row.id))
    ).scalars().all()
    assert len(forecast_rows) > 0
    horizons = {row.horizon for row in forecast_rows}
    assert horizons == {"DAILY", "WEEKLY", "MONTHLY"}

    llm_row = (
        await db_session.execute(select(LLMAnalysisSnapshotRow).where(LLMAnalysisSnapshotRow.research_run_id == run_row.id))
    ).scalar_one()
    assert llm_row.model == "test-model"

    report_row = (
        await db_session.execute(
            select(ResearchReportSnapshotRow).where(ResearchReportSnapshotRow.research_run_id == run_row.id)
        )
    ).scalar_one()
    assert report_row.report_data is not None


@pytest.mark.asyncio
async def test_forecast_snapshot_persists_unavailable_points_with_null_price(db_session):
    # No market_data_service configured (market_data_service=None) means
    # no recent_prices at all -- every technical/price-trend method comes
    # back UNAVAILABLE. That must still be persisted, not dropped.
    fetcher = FakeFinancialDataFetcher()
    analyst = FakeAnalystService()
    service = _build_service(fetcher, analyst, clock=_clock_at(NOW))

    result = await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))

    forecast_rows = (
        await db_session.execute(
            select(ForecastSnapshotRow).where(ForecastSnapshotRow.research_run_id == result.research_run_id)
        )
    ).scalars().all()
    assert len(forecast_rows) > 0
    assert all(row.predicted_price is None for row in forecast_rows)
    assert all(row.status == "unavailable" for row in forecast_rows)
    assert all(row.metadata_json and "reason" in row.metadata_json for row in forecast_rows)


@pytest.mark.asyncio
async def test_second_identical_request_reuses_snapshot_without_new_calls(db_session):
    fetcher = FakeFinancialDataFetcher()
    analyst = FakeAnalystService()
    service = _build_service(fetcher, analyst, clock=_clock_at(NOW))

    first = await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))
    second = await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))

    assert first.is_new_run is True
    assert second.is_new_run is False
    assert second.research_run_id == first.research_run_id
    assert fetcher.calls == 1  # unchanged from after the first (fresh) run -- reuse never fetches
    assert fetcher.provider_fetches == 1  # never fetched a second time
    assert analyst.calls == 1  # LLM not called again either


# --- request-level financial-data dedup + HUDCO-style fallback recovery -------------


@pytest.mark.asyncio
async def test_financial_data_fetched_exactly_once_per_fresh_run(db_session):
    fetcher = FakeFinancialDataFetcher()
    analyst = FakeAnalystService()
    service = _build_service(fetcher, analyst, clock=_clock_at(NOW))

    await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))

    # One fetch total for the whole request -- raw-data capture and
    # AnalysisApplicationService reuse the same FinancialDataFetchResult,
    # not two independent calls.
    assert fetcher.calls == 1


@pytest.mark.asyncio
async def test_hudco_like_fallback_data_produces_a_completed_run_not_failed(db_session):
    # Mirrors what IndianAPIProvider's /historical_stats fallback
    # actually produces for a ticker like HUDCO: balance sheet + cash
    # flow statements present, income_statements empty (no annual P&L
    # source in the fallback) -- this must reach a usable, non-FAILED
    # result rather than repeating the old "no 'financials' list" failure.
    hudco_financials = CompanyFinancials(
        company_name="Housing & Urban Development Corporation Ltd",
        ticker="HUDCO",
        currency="INR",
        fiscal_periods=["FY2026"],
        income_statements=[],
        balance_sheets=[BalanceSheet(period="FY2026", total_debt=d(141677), total_assets=d(166838))],
        cash_flow_statements=[CashFlowStatement(period="FY2026", operating_cash_flow=d(-33912), free_cash_flow=d(-33906))],
    )
    fetcher = FakeFinancialDataFetcher(company_financials=hudco_financials)
    analyst = FakeAnalystService()
    service = _build_service(fetcher, analyst, clock=_clock_at(NOW))

    result = await service.run_research(db_session, ResearchRunRequest(ticker="HUDCO"))

    assert result.status != ResearchRunStatus.FAILED
    assert result.result.status.value != "failed"
    assert result.result.financial_analysis is not None
    assert fetcher.calls == 1


# --- daily price accumulation into daily_price_history --------------------------------


@pytest.mark.asyncio
async def test_fresh_run_accumulates_todays_price_into_daily_price_history(db_session):
    from sqlalchemy import select

    from app.db.models import DailyPriceHistoryRow

    fetcher = FakeFinancialDataFetcher()
    analyst = FakeAnalystService()
    market = FakeMarketDataFetcher(base_price=100)
    service = _build_service(fetcher, analyst, clock=_clock_at(NOW), market_fetcher=market)

    await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))

    row = (
        await db_session.execute(
            select(DailyPriceHistoryRow).where(
                DailyPriceHistoryRow.ticker == "ACME", DailyPriceHistoryRow.date == NOW.date()
            )
        )
    ).scalar_one()
    assert row.source == "yfinance_daily"
    assert row.price is not None


# --- same-day reuse still gets a fresh market quote ----------------------------------


@pytest.mark.asyncio
async def test_same_day_reuse_fetches_fresh_quote_but_not_analysis(db_session):
    fetcher = FakeFinancialDataFetcher()
    analyst = FakeAnalystService()
    market = FakeMarketDataFetcher(base_price=100)
    service = _build_service(fetcher, analyst, clock=_clock_at(NOW), market_fetcher=market)

    first = await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))
    second = await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))

    assert first.is_new_run is True
    assert second.is_new_run is False
    assert second.research_run_id == first.research_run_id

    # expensive analysis/LLM must NOT rerun on the reused path
    assert fetcher.provider_fetches == 1
    assert analyst.calls == 1

    # but the market quote must be fetched again (through the cache) and
    # be different (fresher) from the one baked into the first response.
    # (First run calls get_snapshot twice -- raw-data capture, then
    # AnalysisApplicationService's own resolve -- the reused run adds one more.)
    assert market.calls == 3
    assert second.result.market_quote is not None
    assert second.result.market_quote.current_price != first.result.market_quote.current_price
    assert second.result.report.market.current_price == second.result.market_quote.current_price


@pytest.mark.asyncio
async def test_same_day_reuse_survives_market_fetch_failure(db_session):
    class FailingMarketFetcher:
        async def get_snapshot(self, ticker, include_recent_prices=True):
            raise RuntimeError("provider down")

    fetcher = FakeFinancialDataFetcher()
    analyst = FakeAnalystService()
    service = _build_service(fetcher, analyst, clock=_clock_at(NOW), market_fetcher=FailingMarketFetcher())

    first = await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))
    second = await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))

    assert second.is_new_run is False
    assert second.status == first.status  # reused response still returned, not an error


# --- force refresh: always fresh, never overwrites -----------------------------------


@pytest.mark.asyncio
async def test_force_refresh_creates_new_run_and_preserves_the_previous_one(db_session):
    fetcher = FakeFinancialDataFetcher()
    analyst = FakeAnalystService()
    service = _build_service(fetcher, analyst, clock=_advancing_clock(NOW))

    normal = await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))
    forced = await service.run_research(db_session, ResearchRunRequest(ticker="ACME", force_refresh=True))

    assert forced.research_run_id != normal.research_run_id
    assert forced.run_type == ResearchRunType.FORCE_REFRESH
    assert forced.is_new_run is True
    # force_refresh always re-runs the pipeline (and the LLM), but does
    # NOT bypass the underlying provider TTL cache -- financial
    # statements genuinely haven't changed in the same session, so the
    # provider itself is still only ever fetched once.
    assert fetcher.provider_fetches == 1
    assert analyst.calls == 2  # forced run always calls the LLM again

    # both rows still exist, independently, in history
    all_runs = (await db_session.execute(select(ResearchRunRow).where(ResearchRunRow.ticker == "ACME"))).scalars().all()
    assert {r.id for r in all_runs} == {normal.research_run_id, forced.research_run_id}

    # a subsequent NORMAL request reuses the force-refresh snapshot (the
    # most recent completed run), not the original normal one
    reused = await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))
    assert reused.is_new_run is False
    assert reused.research_run_id == forced.research_run_id
    assert fetcher.provider_fetches == 1
    assert analyst.calls == 2


@pytest.mark.asyncio
async def test_force_refresh_still_recomputes_with_market_data_configured(db_session):
    fetcher = FakeFinancialDataFetcher()
    analyst = FakeAnalystService()
    market = FakeMarketDataFetcher(base_price=100)
    service = _build_service(fetcher, analyst, clock=_advancing_clock(NOW), market_fetcher=market)

    normal = await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))
    forced = await service.run_research(db_session, ResearchRunRequest(ticker="ACME", force_refresh=True))

    assert forced.is_new_run is True
    assert forced.research_run_id != normal.research_run_id
    assert analyst.calls == 2  # full pipeline recomputed, not just the quote overlaid
    assert forced.result.market_quote.current_price != normal.result.market_quote.current_price


# --- LLM reuse-by-hash across different research runs ---------------------------------


@pytest.mark.asyncio
async def test_llm_result_is_reused_across_runs_with_identical_input():
    # A separate db_session isn't injected here -- build one manually so
    # two runs can happen on two different (fake) "days" without the
    # partial-unique-index blocking the second NORMAL/COMPLETED run.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    fetcher = FakeFinancialDataFetcher()
    analyst = FakeAnalystService()

    day1 = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    day2 = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)

    async with session_factory() as session:
        service = _build_service(fetcher, analyst, clock=_clock_at(day1))
        first = await service.run_research(session, ResearchRunRequest(ticker="ACME"))

    async with session_factory() as session:
        service = _build_service(fetcher, analyst, clock=_clock_at(day2))
        second = await service.run_research(session, ResearchRunRequest(ticker="ACME"))

    assert first.research_run_id != second.research_run_id
    assert fetcher.provider_fetches == 1  # still within the (fake, unexpiring) provider cache
    assert analyst.calls == 1  # the LLM input was byte-identical across both days -> reused
    assert second.result.analyst.status == "success"

    await engine.dispose()


# --- failure handling -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_research_does_not_save_a_report_snapshot_and_allows_retry(db_session):
    failing_fetcher = FakeFinancialDataFetcher(succeed=False)
    analyst = FakeAnalystService()
    service = _build_service(failing_fetcher, analyst, clock=_clock_at(NOW))

    failed = await service.run_research(db_session, ResearchRunRequest(ticker="ACME"))

    assert failed.status == ResearchRunStatus.FAILED
    assert failed.result.status.value == "failed"
    run_row = await db_session.get(ResearchRunRow, failed.research_run_id)
    assert run_row.status == "FAILED"
    assert run_row.error_message is not None

    report_rows = (
        await db_session.execute(
            select(ResearchReportSnapshotRow).where(ResearchReportSnapshotRow.research_run_id == failed.research_run_id)
        )
    ).scalars().all()
    assert report_rows == []
    assert analyst.calls == 0  # never reached the LLM stage

    # retry with a working fetcher succeeds -- the FAILED row must not
    # permanently occupy today's NORMAL slot.
    working_fetcher = FakeFinancialDataFetcher()
    service2 = _build_service(working_fetcher, analyst, clock=_clock_at(NOW))
    retried = await service2.run_research(db_session, ResearchRunRequest(ticker="ACME"))
    assert retried.status == ResearchRunStatus.COMPLETED
    assert retried.research_run_id != failed.research_run_id
