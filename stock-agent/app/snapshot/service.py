"""Persistent, dated research snapshots.

`ResearchSnapshotService.run_research` is the one entry point: given a
ticker (+ optional `force_refresh`), it either replays an already-saved
snapshot for today (no provider calls, no LLM call) or runs a full
analysis and saves every stage of it, permanently, so it can be
replayed later without recomputation. It performs NO calculation of its
own -- financial/valuation/scoring/forecasting stay exactly as
deterministic as they already were, and the LLM is only ever asked to
interpret results this module already computed elsewhere
(`AnalysisPipelineService`, `AnalystService`).

Concurrency: `ResearchRunRow`'s partial unique index (see
`app/db/models.py`) makes two concurrent NORMAL requests for the same
ticker+date fail with `IntegrityError` on whichever inserts second --
this module catches that and returns the winner's result once it
completes. What it does NOT do is wait/poll for a genuinely
in-flight RUNNING request from a different process; that would need a
real distributed lock, which this single-user, single-process
application does not need. See `ResearchInProgressError`.
"""

import hashlib
import json
import logging
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.service import AnalysisApplicationService
from app.data.daily_price_history_service import upsert_daily_price
from app.data.models import CompanyIdentifier, FinancialDataFetchResult
from app.data.service import FinancialDataFetcher
from app.db.models import (
    ForecastSnapshotRow,
    LLMAnalysisSnapshotRow,
    RawResearchDataRow,
    ResearchAnalysisSnapshotRow,
    ResearchReportSnapshotRow,
    ResearchRunRow,
)
from app.forecasting.accuracy_service import ForecastAccuracyService
from app.market.service import MarketDataFetcher
from app.models.analyst import AnalystResult
from app.models.financial_statements import CompanyFinancials
from app.models.forecasting import ForecastResult
from app.models.research_run import (
    ForecastHorizonKey,
    RawDataType,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchRunStatus,
    ResearchRunType,
)
from app.pipeline.models import CombinedAnalysisResult, PipelineStatus, ResearchOptions, TickerAnalysisRequest
from app.reporting.service import ReportService
from app.snapshot.exceptions import ResearchInProgressError
from app.snapshot.hashing import compute_input_hash
from app.snapshot.versions import CALCULATION_VERSION, DATA_VERSION, FORECAST_VERSION, PROMPT_VERSION

logger = logging.getLogger(__name__)


async def overlay_fresh_quote(
    market_data_service: MarketDataFetcher | None, result: ResearchRunResult, ticker: str
) -> ResearchRunResult:
    """Splices a live quote into an already-saved `ResearchRunResult`,
    never recomputing anything else -- financial analysis/valuation/
    scoring/forecast are expensive (the LLM call alone can take ~1-2
    minutes) and don't change intraday, but the *price* is cheap (one
    cached call, ~30s TTL) and stale within minutes. Used both by
    `ResearchSnapshotService.run_research`'s same-day reuse path and by
    `GET /api/v1/research/{ticker}` (a plain read, i.e. "open this
    stock") -- without this, opening a stock only ever showed whatever
    price was frozen into the report at whatever time it was originally
    computed, even hours or days stale, with no live quote at all.
    Never fails the request if the quote fetch fails -- worst case, the
    saved snapshot's original price stands.
    """
    if market_data_service is None or result.result is None:
        return result
    try:
        snapshot_result = await market_data_service.get_snapshot(ticker, include_recent_prices=False)
    except Exception as exc:  # noqa: BLE001 - overlay is best-effort, never blocks the response
        logger.warning("fresh_quote_overlay_failed ticker=%s error=%s", ticker, exc)
        return result

    if snapshot_result.status != "success" or snapshot_result.snapshot is None or snapshot_result.snapshot.quote is None:
        return result

    combined = result.result.model_copy(update={"market_quote": snapshot_result.snapshot.quote})
    if combined.report is not None:
        combined = combined.model_copy(update={"report": ReportService().generate(combined)})
    return result.model_copy(update={"result": combined})


class AnalystAnalyzer(Protocol):
    async def analyze(
        self, financial_analysis, valuation, scoring, company_financials=None, research=None
    ) -> AnalystResult: ...


class ResearchSnapshotService:
    def __init__(
        self,
        *,
        application_service: AnalysisApplicationService,
        financial_data_service: FinancialDataFetcher,
        market_data_service: MarketDataFetcher | None,
        analyst_service: AnalystAnalyzer,
        financial_data_provider_name: str,
        market_data_provider_name: str | None,
        llm_provider_name: str,
        model_version: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._application_service = application_service
        self._financial_data_service = financial_data_service
        self._market_data_service = market_data_service
        self._analyst_service = analyst_service
        self._financial_data_provider_name = financial_data_provider_name
        self._market_data_provider_name = market_data_provider_name
        self._llm_provider_name = llm_provider_name
        self._model_version = model_version
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def run_research(self, db: AsyncSession, request: ResearchRunRequest) -> ResearchRunResult:
        ticker = request.ticker.strip().upper()
        started_at = self._clock()
        today = started_at.date()

        if not request.force_refresh:
            existing = await self._find_reusable_run(db, ticker, today)
            if existing is not None:
                logger.info(
                    "research_snapshot_reused research_run_id=%s ticker=%s research_date=%s",
                    existing.id, ticker, today,
                )
                reused = await self._load_result(db, existing, is_new_run=False)
                return await overlay_fresh_quote(self._market_data_service, reused, ticker)

        run_type = ResearchRunType.FORCE_REFRESH if request.force_refresh else ResearchRunType.NORMAL
        run_row = ResearchRunRow(
            ticker=ticker, research_date=today, started_at=started_at,
            status=ResearchRunStatus.RUNNING.value, run_type=run_type.value,
            data_version=DATA_VERSION, calculation_version=CALCULATION_VERSION,
            forecast_version=FORECAST_VERSION, prompt_version=PROMPT_VERSION,
            model_version=self._model_version,
        )
        db.add(run_row)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            existing = await self._find_reusable_run(db, ticker, today)
            if existing is not None:
                logger.info(
                    "research_snapshot_reused_after_race research_run_id=%s ticker=%s research_date=%s",
                    existing.id, ticker, today,
                )
                return await self._load_result(db, existing, is_new_run=False)
            raise ResearchInProgressError(
                f"Research for {ticker} on {today} is already in progress in another request."
            ) from None

        logger.info(
            "research_run_created research_run_id=%s ticker=%s research_date=%s run_type=%s",
            run_row.id, ticker, today, run_type.value,
        )
        if request.force_refresh:
            logger.info("force_refresh_started research_run_id=%s ticker=%s", run_row.id, ticker)

        company_financials, financial_fetch_result = await self._capture_raw_financial(db, run_row, ticker)
        if self._market_data_service is not None:
            await self._capture_raw_market(db, run_row, ticker, request.include_price_trend_forecast)

        ticker_request = TickerAnalysisRequest(
            ticker=ticker,
            include_price_trend_forecast=request.include_price_trend_forecast,
            research=ResearchOptions(enabled=request.research_enabled),
        )
        # Reuse the same fetch raw capture just made -- avoids a second,
        # independent /stock (or /historical_stats fallback) round-trip
        # for the same ticker within one research request.
        combined = await self._application_service.analyze_by_ticker(
            ticker_request, run_analyst=False, financial_fetch_result=financial_fetch_result
        )

        if combined.status == PipelineStatus.FAILED:
            error_message = "; ".join(combined.warnings) or "Research failed for an unknown reason."
            await self._mark_failed(db, run_row, error_message)
            logger.warning("research_failed research_run_id=%s ticker=%s reason=%s", run_row.id, ticker, error_message)
            return ResearchRunResult(
                research_run_id=run_row.id, ticker=ticker, research_date=today, run_type=run_type,
                status=ResearchRunStatus.FAILED, is_new_run=True,
                started_at=run_row.started_at, completed_at=run_row.completed_at, result=combined,
            )

        await self._save_analysis_snapshot(db, run_row, combined)
        if combined.forecast is not None:
            await self._save_forecast_snapshots(db, run_row, ticker, today, combined.forecast)

        analyst_result = await self._resolve_analyst(
            db, run_row, ticker, combined, company_financials, request.force_refresh
        )
        final_status = PipelineStatus.CALCULATED if analyst_result.status == "success" else PipelineStatus.PARTIAL
        combined = combined.model_copy(update={"analyst": analyst_result, "status": final_status})

        report = ReportService().generate(combined)
        combined = combined.model_copy(update={"report": report})
        await self._save_report_snapshot(db, run_row, ticker, today, combined)

        run_row.status = (
            ResearchRunStatus.COMPLETED if final_status == PipelineStatus.CALCULATED else ResearchRunStatus.PARTIAL
        ).value
        run_row.completed_at = self._clock()
        await db.commit()

        logger.info("research_run_completed research_run_id=%s ticker=%s status=%s", run_row.id, ticker, run_row.status)
        if request.force_refresh:
            logger.info("force_refresh_completed research_run_id=%s ticker=%s", run_row.id, ticker)

        return ResearchRunResult(
            research_run_id=run_row.id, ticker=ticker, research_date=today, run_type=run_type,
            status=ResearchRunStatus(run_row.status), is_new_run=True,
            started_at=run_row.started_at, completed_at=run_row.completed_at, result=combined,
        )

    # --- reuse lookup -----------------------------------------------------------------

    async def _find_reusable_run(self, db: AsyncSession, ticker: str, research_date: date) -> ResearchRunRow | None:
        """The latest usable (COMPLETED or PARTIAL) run for this
        ticker+date, regardless of `run_type` -- a force-refresh done
        earlier today is a perfectly good snapshot for a later NORMAL
        request to reuse; `run_type` is provenance, not a reuse filter."""
        # `created_at` is a secondary sort key purely to make ordering
        # deterministic if `completed_at` ever ties (e.g. two runs
        # finishing within the same clock tick) -- still not a
        # guaranteed *chronological* tiebreak (both columns share the
        # same clock resolution), just a documented, repeatable one.
        stmt = (
            select(ResearchRunRow)
            .where(
                ResearchRunRow.ticker == ticker,
                ResearchRunRow.research_date == research_date,
                ResearchRunRow.status.in_([ResearchRunStatus.COMPLETED.value, ResearchRunStatus.PARTIAL.value]),
            )
            .order_by(ResearchRunRow.completed_at.desc(), ResearchRunRow.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _load_result(self, db: AsyncSession, run_row: ResearchRunRow, is_new_run: bool) -> ResearchRunResult:
        stmt = select(ResearchReportSnapshotRow).where(ResearchReportSnapshotRow.research_run_id == run_row.id)
        result = await db.execute(stmt)
        report_row = result.scalar_one()
        combined = CombinedAnalysisResult.model_validate_json(report_row.report_data)
        return ResearchRunResult(
            research_run_id=run_row.id, ticker=run_row.ticker, research_date=run_row.research_date,
            run_type=ResearchRunType(run_row.run_type), status=ResearchRunStatus(run_row.status),
            is_new_run=is_new_run, started_at=run_row.started_at, completed_at=run_row.completed_at,
            result=combined,
        )

    # --- raw capture --------------------------------------------------------------------

    @staticmethod
    async def _rollback_quietly(db: AsyncSession, *keep) -> None:
        """Return the session to a usable state after a swallowed failure.

        Without this, a failure inside a best-effort block leaves the
        session needing a rollback, and the next unrelated `add()`/
        `commit()` raises `PendingRollbackError` -- so a bookkeeping
        problem aborts the whole research run. Every call site sits after
        its own commit, so nothing still needed is discarded.

        Rollback also expires every loaded instance, so rows the run still
        reads from (`run_row`) are refreshed explicitly -- otherwise the
        next attribute access would attempt a lazy load and raise
        `MissingGreenlet`."""
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001 - a failed rollback must not mask the original failure
            logger.warning("session_rollback_failed", exc_info=True)
            return
        for instance in keep:
            try:
                await db.refresh(instance)
            except Exception:  # noqa: BLE001 - best-effort; the run continues either way
                logger.warning("session_refresh_failed", exc_info=True)

    async def _capture_raw_financial(
        self, db: AsyncSession, run_row: ResearchRunRow, ticker: str
    ) -> tuple[CompanyFinancials | None, FinancialDataFetchResult | None]:
        """Also returns the raw `FinancialDataFetchResult` so the caller
        can hand it straight to `AnalysisApplicationService.analyze_by_ticker`
        instead of fetching financials a second time for the same
        request (see `run_research`) -- this is the one financial-data
        fetch for the whole request, success or failure alike."""
        try:
            fetch_result = await self._financial_data_service.get_company_financials(
                CompanyIdentifier(ticker=ticker)
            )
        except Exception as exc:  # noqa: BLE001 - raw capture is best-effort, never blocks the run
            logger.warning(
                "raw_data_capture_failed research_run_id=%s ticker=%s data_type=%s error=%s",
                run_row.id, ticker, RawDataType.FINANCIAL_STATEMENTS.value, exc,
            )
            await self._rollback_quietly(db, run_row)
            return None, None

        await self._save_raw(
            db, run_row, ticker, self._financial_data_provider_name, RawDataType.FINANCIAL_STATEMENTS,
            request_metadata={"ticker": ticker}, response_json=fetch_result.model_dump_json(),
        )
        if fetch_result.status == "success" and fetch_result.data is not None:
            return fetch_result.data.company_financials, fetch_result
        return None, fetch_result

    async def _capture_raw_market(
        self, db: AsyncSession, run_row: ResearchRunRow, ticker: str, include_recent_prices: bool
    ) -> None:
        try:
            snapshot_result = await self._market_data_service.get_snapshot(
                ticker, include_recent_prices=include_recent_prices
            )
        except Exception as exc:  # noqa: BLE001 - raw capture is best-effort, never blocks the run
            logger.warning(
                "raw_data_capture_failed research_run_id=%s ticker=%s data_type=%s error=%s",
                run_row.id, ticker, RawDataType.MARKET_SNAPSHOT.value, exc,
            )
            await self._rollback_quietly(db, run_row)
            return
        await self._save_raw(
            db, run_row, ticker, self._market_data_provider_name or "unknown", RawDataType.MARKET_SNAPSHOT,
            request_metadata={"include_recent_prices": include_recent_prices},
            response_json=snapshot_result.model_dump_json(),
        )
        await self._accumulate_daily_price(db, run_row, ticker, snapshot_result)

    async def _accumulate_daily_price(
        self, db: AsyncSession, run_row: ResearchRunRow, ticker: str, snapshot_result
    ) -> None:
        """Persists today's fetched quote into `daily_price_history` --
        this is what lets the store grow one real day at a time from
        ordinary research runs, on top of any one-time Screener backfill
        (see `app.data.daily_price_history_service`). Never blocks the
        run: this is purely additive bookkeeping, not part of the
        analysis result itself."""
        if snapshot_result.status != "success" or snapshot_result.snapshot is None:
            return
        quote = snapshot_result.snapshot.quote
        if quote is None or quote.current_price is None:
            return
        recent_prices = snapshot_result.snapshot.recent_prices
        volume = recent_prices[-1].volume if recent_prices else None
        try:
            await upsert_daily_price(
                db, ticker, run_row.research_date, source="yfinance_daily",
                price=quote.current_price, volume=volume,
            )
            await db.commit()
        except Exception as exc:  # noqa: BLE001 - best-effort bookkeeping, never blocks the run
            logger.warning(
                "daily_price_history_accumulation_failed research_run_id=%s ticker=%s error=%s",
                run_row.id, ticker, exc,
            )
            await self._rollback_quietly(db, run_row)
            return

        try:
            evaluated = await ForecastAccuracyService().evaluate_ticker(db, ticker, as_of=run_row.research_date)
        except Exception as exc:  # noqa: BLE001 - best-effort bookkeeping, never blocks the run
            logger.warning(
                "forecast_accuracy_evaluation_failed research_run_id=%s ticker=%s error=%s",
                run_row.id, ticker, exc,
            )
            await self._rollback_quietly(db, run_row)
            return
        if evaluated:
            logger.info(
                "forecast_accuracy_evaluated_from_research research_run_id=%s ticker=%s rows=%d",
                run_row.id, ticker, evaluated,
            )

    async def _save_raw(
        self, db, run_row, ticker, provider, data_type: RawDataType, *, request_metadata: dict, response_json: str
    ) -> None:
        content_hash = hashlib.sha256(response_json.encode("utf-8")).hexdigest()
        row = RawResearchDataRow(
            research_run_id=run_row.id, ticker=ticker, provider=provider, data_type=data_type.value,
            request_metadata=json.dumps(request_metadata, default=str), response_data=response_json,
            content_hash=content_hash, fetched_at=self._clock(),
        )
        db.add(row)
        await db.commit()
        logger.info(
            "raw_data_saved research_run_id=%s ticker=%s data_type=%s provider=%s",
            run_row.id, ticker, data_type.value, provider,
        )

    # --- deterministic analysis + forecast snapshots --------------------------------------

    async def _save_analysis_snapshot(self, db: AsyncSession, run_row: ResearchRunRow, combined) -> None:
        row = ResearchAnalysisSnapshotRow(
            research_run_id=run_row.id, ticker=run_row.ticker, analysis_version=CALCULATION_VERSION,
            financial_analysis_json=combined.financial_analysis.model_dump_json(),
            valuation_json=combined.valuation.model_dump_json() if combined.valuation else None,
            scoring_json=combined.scoring.model_dump_json() if combined.scoring else None,
        )
        db.add(row)
        await db.commit()
        logger.info("analysis_completed research_run_id=%s ticker=%s", run_row.id, run_row.ticker)

    async def _save_forecast_snapshots(
        self, db: AsyncSession, run_row: ResearchRunRow, ticker: str, prediction_date: date, forecast: ForecastResult
    ) -> None:
        if forecast.horizons is None:
            logger.info("forecast_completed research_run_id=%s ticker=%s rows=0", run_row.id, ticker)
            return

        rows: list[ForecastSnapshotRow] = []
        for horizon_key, horizon_forecast in (
            (ForecastHorizonKey.DAILY, forecast.horizons.daily),
            (ForecastHorizonKey.WEEKLY, forecast.horizons.weekly),
            (ForecastHorizonKey.MONTHLY, forecast.horizons.monthly),
        ):
            trend = horizon_forecast.price_trend
            if trend.points:
                for point in trend.points:
                    rows.append(
                        self._forecast_row(
                            run_row, ticker, horizon_key, "linear_regression", prediction_date,
                            target_date=date.fromisoformat(point.date) if point.date else None,
                            period_index=point.period, predicted_price=point.projected_price,
                            status=trend.status.value, reason=trend.reason,
                        )
                    )
            else:
                # No per-period points at all (e.g. insufficient history)
                # -- still record that this method was attempted and why
                # it produced nothing, via a sentinel row (period_index=0
                # is not a real period; it only ever appears here).
                rows.append(
                    self._forecast_row(
                        run_row, ticker, horizon_key, "linear_regression", prediction_date,
                        target_date=None, period_index=0, predicted_price=None,
                        status=trend.status.value, reason=trend.reason,
                    )
                )

            for method in horizon_forecast.technical.methods:
                rows.append(
                    self._forecast_row(
                        run_row, ticker, horizon_key, method.method, prediction_date,
                        target_date=date.fromisoformat(method.projected_date) if method.projected_date else None,
                        period_index=method.horizon_period, predicted_price=method.projected_price,
                        status=method.status.value, reason=method.reason,
                    )
                )

        db.add_all(rows)
        await db.commit()
        logger.info("forecast_completed research_run_id=%s ticker=%s rows=%d", run_row.id, ticker, len(rows))

    def _forecast_row(
        self, run_row, ticker, horizon_key: ForecastHorizonKey, method: str, prediction_date: date,
        *, target_date, period_index: int, predicted_price, status: str, reason: str | None,
    ) -> ForecastSnapshotRow:
        return ForecastSnapshotRow(
            research_run_id=run_row.id, ticker=ticker, horizon=horizon_key.value, method=method,
            prediction_date=prediction_date, target_date=target_date, period_index=period_index,
            predicted_price=predicted_price, status=status,
            metadata_json=json.dumps({"reason": reason} if reason else {}),
            forecast_version=FORECAST_VERSION,
        )

    # --- LLM (analyst) reuse-by-hash -------------------------------------------------------

    async def _resolve_analyst(
        self, db: AsyncSession, run_row: ResearchRunRow, ticker: str, combined,
        company_financials: CompanyFinancials | None, force_refresh: bool,
    ) -> AnalystResult:
        financial_dict = combined.financial_analysis.model_dump(mode="json") if combined.financial_analysis else {}
        valuation_dict = combined.valuation.model_dump(mode="json") if combined.valuation else None
        scoring_dict = combined.scoring.model_dump(mode="json") if combined.scoring else {}
        research_dict = combined.research.model_dump(mode="json") if combined.research else None

        input_hash = compute_input_hash(
            financial_analysis=financial_dict, valuation=valuation_dict, scoring=scoring_dict,
            research=research_dict, prompt_version=PROMPT_VERSION, model=self._model_version,
        )

        if not force_refresh:
            cached = await self._find_llm_snapshot(db, ticker, input_hash)
            if cached is not None:
                logger.info(
                    "llm_cache_hit research_run_id=%s ticker=%s input_hash=%s",
                    run_row.id, ticker, input_hash[:12],
                )
                return AnalystResult.model_validate_json(cached.response_json)

        logger.info("llm_generation research_run_id=%s ticker=%s input_hash=%s", run_row.id, ticker, input_hash[:12])
        analyst_result = await self._analyst_service.analyze(
            combined.financial_analysis, combined.valuation, combined.scoring, company_financials, combined.research
        )

        if analyst_result.status == "success":
            # Only successful responses are cached/reused -- a transient
            # LLM failure must never be "remembered" as permanent, since
            # that would make a temporary outage unrecoverable until the
            # deterministic inputs themselves change.
            snapshot_row = LLMAnalysisSnapshotRow(
                research_run_id=run_row.id, ticker=ticker, provider=self._llm_provider_name,
                model=self._model_version, prompt_version=PROMPT_VERSION, input_hash=input_hash,
                input_snapshot=json.dumps(
                    {"financial_analysis": financial_dict, "valuation": valuation_dict, "scoring": scoring_dict,
                     "research": research_dict}, default=str,
                ),
                response_json=analyst_result.model_dump_json(),
            )
            db.add(snapshot_row)
            await db.commit()
        return analyst_result

    async def _find_llm_snapshot(self, db: AsyncSession, ticker: str, input_hash: str) -> LLMAnalysisSnapshotRow | None:
        stmt = (
            select(LLMAnalysisSnapshotRow)
            .where(LLMAnalysisSnapshotRow.ticker == ticker, LLMAnalysisSnapshotRow.input_hash == input_hash)
            .order_by(LLMAnalysisSnapshotRow.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # --- final report snapshot + failure handling -------------------------------------------

    async def _save_report_snapshot(self, db: AsyncSession, run_row, ticker: str, research_date: date, combined) -> None:
        row = ResearchReportSnapshotRow(
            research_run_id=run_row.id, ticker=ticker, research_date=research_date,
            report_data=combined.model_dump_json(),
        )
        db.add(row)
        await db.commit()

    async def _mark_failed(self, db: AsyncSession, run_row: ResearchRunRow, message: str) -> None:
        run_row.status = ResearchRunStatus.FAILED.value
        run_row.error_message = message[:4000]
        run_row.completed_at = self._clock()
        await db.commit()
