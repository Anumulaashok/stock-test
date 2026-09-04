"""API-facing models for persistent research snapshots (`app/snapshot/`).

Distinct from `app/models/research.py` (`ResearchResult` etc.), which is
the Finnhub news-enrichment domain -- these models are about *saving and
replaying a whole analysis run*, not fetching news. See
`app/db/models.py`'s research-snapshot section for the corresponding
ORM rows this API layer is built from.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.pipeline.models import CombinedAnalysisResult


class ResearchRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class ResearchRunType(StrEnum):
    NORMAL = "NORMAL"
    FORCE_REFRESH = "FORCE_REFRESH"


class RawDataType(StrEnum):
    """Reflects this app's actual provider fetch granularity (see
    `app/data/`, `app/market/`, `app/research/`) -- financial statements
    and market quote+history are each one bundled provider call, not
    separate balance-sheet/cash-flow/income-statement requests."""

    FINANCIAL_STATEMENTS = "FINANCIAL_STATEMENTS"
    MARKET_SNAPSHOT = "MARKET_SNAPSHOT"
    NEWS = "NEWS"
    OTHER = "OTHER"


class ForecastHorizonKey(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class RecentResearchEntry(BaseModel):
    """One row of `GET /api/v1/research/recent` -- the latest
    COMPLETED/PARTIAL run for one ticker, across every ticker ever
    researched (not scoped to any user's watchlist; research has no
    `user_id`, see `app/db/models.py`). `company_name`/`overall_score`/
    `band` are read from the run's persisted `ResearchAnalysisSnapshotRow`
    rather than the full (much larger) saved report, so this list stays
    cheap regardless of how big a report is. Both are `None` only when
    the run's analysis snapshot itself is missing/unparseable -- never a
    fabricated placeholder."""

    ticker: str
    company_name: str | None
    research_run_id: str
    research_date: date
    status: ResearchRunStatus
    run_type: ResearchRunType
    overall_score: Decimal | None
    band: str | None
    completed_at: datetime | None = None


class ResearchRunSummary(BaseModel):
    """One row of research history -- enough to render a history list
    without loading the (potentially large) saved report."""

    id: str
    ticker: str
    research_date: date
    run_type: ResearchRunType
    status: ResearchRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class ResearchRunResult(BaseModel):
    """What `POST /api/v1/research/ticker` returns -- the same
    `CombinedAnalysisResult` shape `/api/v1/analyze/ticker` already
    returns (`result`), plus the snapshot metadata the frontend needs to
    show "Research snapshot · Sep 2, 2026" and whether this call did new
    work or reused an existing one."""

    research_run_id: str
    ticker: str
    research_date: date
    run_type: ResearchRunType
    status: ResearchRunStatus
    is_new_run: bool = Field(
        description="True if this call performed a fresh run just now; "
        "False if an already-completed snapshot was reused."
    )
    started_at: datetime
    completed_at: datetime | None = None
    result: CombinedAnalysisResult


class ResearchRunRequest(BaseModel):
    """Mirrors `app.pipeline.models.TickerAnalysisRequest` plus the one
    new field this feature adds. Kept separate (not a subclass) so the
    existing, unauthenticated `/api/v1/analyze/ticker` request shape
    never has to know this field exists."""

    ticker: str
    force_refresh: bool = Field(
        default=False,
        description="Ignore today's completed snapshot (if any) and run "
        "a full fresh analysis, saved as a new, additional run -- never "
        "overwrites the previous one.",
    )
    include_price_trend_forecast: bool = True
    research_enabled: bool = False


class ForecastSnapshotEntry(BaseModel):
    """One persisted forecasting-method projection for one target date."""

    id: str
    research_run_id: str
    ticker: str
    horizon: ForecastHorizonKey
    method: str
    prediction_date: date
    target_date: date | None
    period_index: int
    predicted_price: Decimal | None
    status: str
    reason: str | None = None


class ResearchStageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ResearchStage(BaseModel):
    key: str
    label: str
    status: ResearchStageStatus
    detail: str | None = None


class ResearchProgress(BaseModel):
    """Real, best-effort progress for an in-flight (or just-finished)
    research run -- see `app.snapshot.progress`. `finished=True` once
    the run this reflects has reached a terminal state; the frontend
    stops polling at that point rather than on a fixed timer."""

    ticker: str
    research_run_id: str | None
    finished: bool
    stages: list[ResearchStage]


class PredictionOutcome(BaseModel):
    """Foundation for future accuracy evaluation -- populated by a later,
    separate evaluation pass, not by this feature. `actual_price` and
    everything derived from it are `None` until evaluated."""

    id: str
    forecast_snapshot_id: str
    ticker: str
    target_date: date
    predicted_price: Decimal
    actual_price: Decimal | None = None
    absolute_error: Decimal | None = None
    percentage_error: Decimal | None = None
    direction_correct: bool | None = None
    evaluated_at: datetime | None = None
