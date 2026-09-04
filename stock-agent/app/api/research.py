"""Persistent research-snapshot API.

Distinct from `POST /api/v1/analyze/ticker` (`app/api/analyze.py`),
which always computes fresh and never persists anything --
`POST /api/v1/research/ticker` is the snapshot-aware entry point:
normal calls reuse today's already-completed research for the ticker
(no provider or LLM calls), `force_refresh` always computes and saves a
new one, and nothing is ever overwritten. The GET routes below never
trigger a recomputation of financial analysis/valuation/scoring/
forecast/LLM narrative -- they only ever replay what was already saved
for those. `GET /{ticker}` (the "open this stock" read) is the one
exception that does still make a live call: it overlays a fresh quote
on top of the saved report the same way a same-day `POST /ticker` reuse
does (see `app.snapshot.service.overlay_fresh_quote`), because a saved
snapshot's price can otherwise sit frozen at whatever it was when the
report was originally computed, hours or days stale.
"""

import json
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import build_data_source_manager, build_research_snapshot_service
from app.core.config import Settings, get_settings
from app.data.factory import get_financial_data_provider
from app.db.base import get_db
from app.db.models import (
    ForecastSnapshotRow,
    ResearchAnalysisSnapshotRow,
    ResearchReportSnapshotRow,
    ResearchRunRow,
)
from app.models.research_run import (
    ForecastHorizonKey,
    ForecastSnapshotEntry,
    RecentResearchEntry,
    ResearchProgress,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchRunStatus,
    ResearchRunSummary,
    ResearchRunType,
    ResearchStage,
)
from app.pipeline.models import CombinedAnalysisResult, PipelineCompanyInfo, PipelineStatus
from app.snapshot import progress as progress_module
from app.snapshot.service import overlay_fresh_quote
from app.snapshot.exceptions import ResearchInProgressError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research"])


def _normalize(ticker: str) -> str:
    return ticker.strip().upper()


@router.post("/ticker")
async def run_research(
    request: ResearchRunRequest,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> ResearchRunResult:
    try:
        get_financial_data_provider(settings)
    except ValueError as exc:
        logger.warning("Financial data provider misconfigured: %s", exc)
        ticker = _normalize(request.ticker)
        now = datetime.now(timezone.utc)
        failed = CombinedAnalysisResult(
            company=PipelineCompanyInfo(name=ticker, ticker=ticker),
            status=PipelineStatus.FAILED,
            warnings=[f"Financial data provider is not configured: {exc}"],
        )
        return ResearchRunResult(
            research_run_id="", ticker=ticker, research_date=now.date(),
            run_type=ResearchRunType.FORCE_REFRESH if request.force_refresh else ResearchRunType.NORMAL,
            status=ResearchRunStatus.FAILED, is_new_run=True,
            started_at=now, completed_at=None,
            result=failed,
        )

    service = build_research_snapshot_service(settings, db)
    try:
        return await service.run_research(db, request)
    except ResearchInProgressError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/recent")
async def get_recent_research(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[RecentResearchEntry]:
    """The latest COMPLETED/PARTIAL run for each ticker ever researched,
    newest first -- global across all tickers, not scoped to any single
    request's watchlist. Backs the Intelligence home page and the
    `/research` history page without the N+1 "fetch the watchlist, then
    one request per ticker" pattern those pages previously would have
    needed. Declared before `GET /{ticker}` so `/recent` is never matched
    as a ticker.
    """
    ranked = (
        select(
            ResearchRunRow.id,
            ResearchRunRow.ticker,
            ResearchRunRow.research_date,
            ResearchRunRow.run_type,
            ResearchRunRow.status,
            ResearchRunRow.completed_at,
            func.row_number()
            .over(partition_by=ResearchRunRow.ticker, order_by=ResearchRunRow.completed_at.desc())
            .label("rn"),
        )
        .where(ResearchRunRow.status.in_([ResearchRunStatus.COMPLETED.value, ResearchRunStatus.PARTIAL.value]))
        .subquery()
    )
    stmt = (
        select(ranked, ResearchAnalysisSnapshotRow.scoring_json)
        .where(ranked.c.rn == 1)
        .outerjoin(ResearchAnalysisSnapshotRow, ResearchAnalysisSnapshotRow.research_run_id == ranked.c.id)
        .order_by(ranked.c.completed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()

    entries = []
    for row in rows:
        company_name: str | None = None
        overall_score: str | None = None
        band: str | None = None
        if row.scoring_json:
            try:
                scoring = json.loads(row.scoring_json)
                company_name = scoring.get("company_name")
                overall_score = scoring.get("overall_score")
                band = scoring.get("band")
            except (json.JSONDecodeError, AttributeError):
                logger.warning("recent_research_scoring_json_unparseable ticker=%s run_id=%s", row.ticker, row.id)
        entries.append(
            RecentResearchEntry(
                ticker=row.ticker,
                company_name=company_name,
                research_run_id=row.id,
                research_date=row.research_date,
                status=ResearchRunStatus(row.status),
                run_type=ResearchRunType(row.run_type),
                overall_score=overall_score,
                band=band,
                completed_at=row.completed_at,
            )
        )
    return entries


@router.get("/{ticker}")
async def get_latest_research(
    ticker: str,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> ResearchRunResult:
    """The latest COMPLETED/PARTIAL snapshot for `ticker` (any date) --
    never recomputes financial analysis/valuation/scoring/forecast/LLM
    narrative, but does overlay a live quote on top (see module
    docstring), so opening a stock always shows a current price rather
    than whatever was frozen into the report at whatever time it was
    originally computed. 404 if nothing has ever been researched for
    this ticker -- call `POST /ticker` first."""
    ticker = _normalize(ticker)
    stmt = (
        select(ResearchRunRow)
        .where(
            ResearchRunRow.ticker == ticker,
            ResearchRunRow.status.in_([ResearchRunStatus.COMPLETED.value, ResearchRunStatus.PARTIAL.value]),
        )
        .order_by(ResearchRunRow.completed_at.desc())
        .limit(1)
    )
    run_row = (await db.execute(stmt)).scalar_one_or_none()
    if run_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No research found for {ticker} yet.")
    result = await _load_run_result(db, run_row)
    # `DataSourceManager` (not the plain single-provider
    # `CachedMarketDataService`) -- it resolves the ticker's
    # provider-specific symbol (e.g. yfinance needs "TCS.NS", not
    # "TCS") and falls back across the whole configured chain, exactly
    # like every other quote fetch in this app.
    manager = build_data_source_manager(settings, db)
    return await overlay_fresh_quote(manager, result, ticker)


@router.get("/{ticker}/progress")
async def get_research_progress(ticker: str) -> ResearchProgress:
    """Real, best-effort stage-by-stage status for an in-flight (or
    just-finished) `POST /ticker` call for this ticker -- see
    `app.snapshot.progress`. Meant to be polled by a client that already
    has a `POST /ticker` request in flight for the same ticker; never
    triggers or blocks on anything itself. 404 when nothing is known
    (never started in this process, or the process restarted since) --
    the frontend falls back to a plain indeterminate loading state in
    that case, not an error.
    """
    ticker = _normalize(ticker)
    run_progress = progress_module.get(ticker)
    if run_progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No research progress known for {ticker}.")
    return ResearchProgress(
        ticker=run_progress.ticker,
        research_run_id=run_progress.research_run_id,
        finished=run_progress.finished,
        stages=[
            ResearchStage(key=s.key, label=s.label, status=s.status.value, detail=s.detail)
            for s in run_progress.stages
        ],
    )


@router.get("/{ticker}/history")
async def get_research_history(
    ticker: str,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[ResearchRunSummary]:
    ticker = _normalize(ticker)
    stmt = select(ResearchRunRow).where(ResearchRunRow.ticker == ticker)
    if date_from is not None:
        stmt = stmt.where(ResearchRunRow.research_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(ResearchRunRow.research_date <= date_to)
    stmt = stmt.order_by(ResearchRunRow.started_at.desc()).limit(limit).offset(offset)

    rows = (await db.execute(stmt)).scalars().all()
    return [
        ResearchRunSummary(
            id=row.id, ticker=row.ticker, research_date=row.research_date,
            run_type=ResearchRunType(row.run_type), status=ResearchRunStatus(row.status),
            started_at=row.started_at, completed_at=row.completed_at, error_message=row.error_message,
        )
        for row in rows
    ]


@router.get("/{ticker}/history/{research_run_id}")
async def get_research_run(ticker: str, research_run_id: str, db: AsyncSession = Depends(get_db)) -> ResearchRunResult:
    """Returns the EXACT saved report for this run -- never regenerated,
    regardless of the run's status (a FAILED run still returns its
    metadata, just with `result.status="failed"` and no report)."""
    ticker = _normalize(ticker)
    run_row = await db.get(ResearchRunRow, research_run_id)
    if run_row is None or run_row.ticker != ticker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research run not found.")
    return await _load_run_result(db, run_row)


@router.get("/{ticker}/predictions")
async def get_predictions(
    ticker: str,
    horizon: ForecastHorizonKey | None = Query(default=None),
    prediction_date: date | None = Query(default=None),
    target_date: date | None = Query(default=None),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ForecastSnapshotEntry]:
    ticker = _normalize(ticker)
    stmt = select(ForecastSnapshotRow).where(ForecastSnapshotRow.ticker == ticker)
    if horizon is not None:
        stmt = stmt.where(ForecastSnapshotRow.horizon == horizon.value)
    if prediction_date is not None:
        stmt = stmt.where(ForecastSnapshotRow.prediction_date == prediction_date)
    if target_date is not None:
        stmt = stmt.where(ForecastSnapshotRow.target_date == target_date)
    stmt = (
        stmt.order_by(ForecastSnapshotRow.prediction_date.desc(), ForecastSnapshotRow.target_date.asc())
        .limit(limit)
        .offset(offset)
    )

    rows = (await db.execute(stmt)).scalars().all()
    entries = []
    for row in rows:
        meta = json.loads(row.metadata_json) if row.metadata_json else {}
        entries.append(
            ForecastSnapshotEntry(
                id=row.id, research_run_id=row.research_run_id, ticker=row.ticker,
                horizon=ForecastHorizonKey(row.horizon), method=row.method,
                prediction_date=row.prediction_date, target_date=row.target_date,
                period_index=row.period_index, predicted_price=row.predicted_price,
                status=row.status, reason=meta.get("reason"),
            )
        )
    return entries


async def _load_run_result(db: AsyncSession, run_row: ResearchRunRow) -> ResearchRunResult:
    stmt = select(ResearchReportSnapshotRow).where(ResearchReportSnapshotRow.research_run_id == run_row.id)
    report_row = (await db.execute(stmt)).scalar_one_or_none()

    if report_row is None:
        # A FAILED run never got a report snapshot -- reconstruct a
        # minimal, honest failure result rather than pretending one exists.
        combined = CombinedAnalysisResult(
            company=PipelineCompanyInfo(name=run_row.ticker, ticker=run_row.ticker),
            status=PipelineStatus.FAILED,
            warnings=[run_row.error_message or "Research failed."],
        )
    else:
        combined = CombinedAnalysisResult.model_validate_json(report_row.report_data)

    return ResearchRunResult(
        research_run_id=run_row.id, ticker=run_row.ticker, research_date=run_row.research_date,
        run_type=ResearchRunType(run_row.run_type), status=ResearchRunStatus(run_row.status),
        is_new_run=False, started_at=run_row.started_at, completed_at=run_row.completed_at, result=combined,
    )
