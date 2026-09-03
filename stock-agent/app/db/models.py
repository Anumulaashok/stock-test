"""SQLAlchemy ORM models — persistence only.

Pydantic domain/API models live under `app/models/` as everywhere else
in this project; these row models are kept separate so persistence
schema changes never leak into API contracts (in particular,
`UserRow.password_hash` must never be serialized directly into a
response — API layers always map to `app.models.user.UserPublic`).
"""

import uuid
from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    portfolios: Mapped[list["PortfolioRow"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    watchlist_items: Mapped[list["WatchlistItemRow"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class PortfolioRow(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="My Portfolio")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user: Mapped["UserRow"] = relationship(back_populates="portfolios")
    holdings: Mapped[list["HoldingRow"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )


class HoldingRow(Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("portfolio_id", "ticker", name="uq_holding_portfolio_ticker"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    portfolio: Mapped["PortfolioRow"] = relationship(back_populates="holdings")


class WatchlistItemRow(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user: Mapped["UserRow"] = relationship(back_populates="watchlist_items")


class CacheEntryRow(Base):
    """Generic TTL cache store -- see `app/cache/`. Value is an opaque
    JSON blob (a serialized Pydantic model); this table has no
    knowledge of what it's caching, only when it expires."""

    __tablename__ = "cache_entries"

    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class RevokedTokenRow(Base):
    """Enables real logout semantics for otherwise-stateless JWTs: the
    token's `jti` is recorded here until its natural expiry."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# --- Research snapshot history (app/snapshot/) -----------------------------------------
#
# Distinct from `app/research/` (Finnhub news enrichment, stored here as
# one RawResearchDataRow of data_type=NEWS per run) and from the
# TTL-based `CacheEntryRow` above (ephemeral, overwritten on every
# refresh). These rows are a permanent, dated history: never overwritten,
# never deleted by this application, one row set per `ResearchRunRow`.
# No `user_id` anywhere in this section -- this app is a single-user,
# personal tool (see `POST /api/v1/analyze/ticker`, which is likewise
# unauthenticated), so research history is global per ticker, not scoped
# per account.


class ResearchRunRow(Base):
    """One research execution for one ticker on one logical research date.

    Uniqueness: a `run_type='NORMAL'` run only claims the
    `(ticker, research_date)` slot once it reaches a *usable* terminal
    state -- `COMPLETED` or `PARTIAL` (deterministic results succeeded
    even if the LLM narrative didn't; still a legitimate, reusable
    result, exactly like `/api/v1/analyze/ticker` already treats
    `status="partial"` as returnable, not an error). A `FAILED` or
    still-`RUNNING` row must NOT block a retry later the same day, so
    `status` is part of the partial index's predicate, not just
    `run_type`. `FORCE_REFRESH` runs are never constrained by it and may
    repeat freely (see `uq_research_run_normal_completed` below). This
    is the DB-native guarantee against two concurrent normal requests
    both doing a full provider+LLM run; it is not a general-purpose
    distributed lock (see `app/snapshot/service.py`'s docstring for the
    documented single-process limitation).
    """

    __tablename__ = "research_runs"
    __table_args__ = (
        Index(
            "uq_research_run_normal_completed",
            "ticker", "research_date",
            unique=True,
            sqlite_where=text("run_type = 'NORMAL' AND status IN ('COMPLETED', 'PARTIAL')"),
            postgresql_where=text("run_type = 'NORMAL' AND status IN ('COMPLETED', 'PARTIAL')"),
        ),
        Index("ix_research_runs_ticker_date", "ticker", "research_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    research_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # PENDING|RUNNING|COMPLETED|FAILED|PARTIAL
    run_type: Mapped[str] = mapped_column(String(16), nullable=False)  # NORMAL|FORCE_REFRESH
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_version: Mapped[str] = mapped_column(String(32), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), nullable=False)
    forecast_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class RawResearchDataRow(Base):
    """A provider response, stored close to verbatim (the full
    `model_dump_json()` of the fetch-result Pydantic model this app's
    provider layer already produces) -- reproducibility, not just the
    transformed values this codebase's calculations derive from it.

    `data_type` reflects this app's actual fetch granularity (see
    `app/data/`, `app/market/`, `app/research/`): financial statements
    and market quote+history are each returned as one bundled provider
    call, not split into separate balance-sheet/cash-flow/etc. requests."""

    __tablename__ = "raw_research_data"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    research_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False)
    request_metadata: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    response_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON, verbatim provider-result model
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ResearchAnalysisSnapshotRow(Base):
    """The deterministic financial/valuation/scoring results for one run
    -- stored as the same Pydantic models' `model_dump_json()`, never
    recomputed values re-typed by hand. One row per research run."""

    __tablename__ = "research_analysis_snapshots"
    __table_args__ = (UniqueConstraint("research_run_id", name="uq_analysis_snapshot_run"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    research_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    analysis_version: Mapped[str] = mapped_column(String(32), nullable=False)
    financial_analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    valuation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    scoring_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ForecastSnapshotRow(Base):
    """One forecasting method's projection for one target date.

    Every point the forecasting engine produced is stored, including
    ones with `predicted_price=NULL` (an unavailable method, e.g.
    SMA-200 with too little price history) -- `metadata_json` carries
    that method's `status`/`reason` verbatim. Dropping unavailable rows
    would silently discard exactly the "which methods worked, and when"
    history this table exists to answer later."""

    __tablename__ = "forecast_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    research_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    horizon: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # DAILY|WEEKLY|MONTHLY
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    prediction_date: Mapped[date_type] = mapped_column(Date, index=True, nullable=False)
    target_date: Mapped[date_type | None] = mapped_column(Date, index=True, nullable=True)
    period_index: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # calculated|unavailable|invalid
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)  # {"reason": ..., "r_squared": ..., ...}
    forecast_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class LLMAnalysisSnapshotRow(Base):
    """One AI-analyst run. `input_hash` is a stable hash (see
    `app/snapshot/hashing.py`) of the exact deterministic inputs the
    analyst was given plus `prompt_version`/`model` -- a later request
    with an identical hash reuses `response_json` instead of calling the
    LLM again, unless force-refreshed."""

    __tablename__ = "llm_analysis_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    research_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    input_snapshot: Mapped[str] = mapped_column(Text, nullable=False)  # JSON, for debugging/audit only
    response_json: Mapped[str] = mapped_column(Text, nullable=False)  # AnalystResult
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ResearchReportSnapshotRow(Base):
    """The final assembled result -- exactly what `/api/v1/analyze/ticker`
    returns today (a `CombinedAnalysisResult`, report attached) -- so
    replaying a historical run never re-runs any calculation."""

    __tablename__ = "research_report_snapshots"
    __table_args__ = (UniqueConstraint("research_run_id", name="uq_report_snapshot_run"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    research_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    research_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    report_data: Mapped[str] = mapped_column(Text, nullable=False)  # CombinedAnalysisResult JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class PredictionOutcomeRow(Base):
    """Foundation for future prediction-accuracy evaluation (Phase 11 is
    intentionally NOT built yet) -- this table is populated later, by a
    small evaluation pass that is not part of this change, comparing
    `ForecastSnapshotRow.predicted_price` against a real observed price
    on `target_date`. Every column is nullable except the identifying
    ones, since a row may be created before an outcome is known."""

    __tablename__ = "prediction_outcomes"
    __table_args__ = (UniqueConstraint("forecast_snapshot_id", name="uq_prediction_outcome_forecast"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    forecast_snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("forecast_snapshots.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    target_date: Mapped[date_type] = mapped_column(Date, index=True, nullable=False)
    predicted_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    actual_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    absolute_error: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    percentage_error: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    direction_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ScreenerCompanyMappingRow(Base):
    """Maps our canonical ticker to Screener.in's opaque numeric company
    id -- Screener has no public ticker-search API. Populated either
    one-at-a-time (via `POST /api/v1/market/{ticker}/historical/import`'s
    request body) or in bulk by pasting one of Screener's own
    company-search JSON results (`POST /api/v1/market/screener-mappings/import`,
    see `app.data.mappers.screener.map_screener_company_list`) --
    `screener_company_mappings` is the reusable, queryable result of
    either path, and `GET /api/v1/market/screener-mappings` searches it
    for the ticker-input autocomplete."""

    __tablename__ = "screener_company_mappings"

    ticker: Mapped[str] = mapped_column(String(32), primary_key=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    screener_company_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    consolidated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class DailyPriceHistoryRow(Base):
    """One ticker's actual daily price/volume, accumulated from two
    sources: a one-time bulk backfill from Screener.in's chart API
    (`source="screener_import"`) and an ongoing daily upsert of whatever
    the configured `MarketDataProvider` returns during normal research
    (`source="yfinance_daily"`, see `app.data.daily_price_history_service`).
    This is the permanent, growing dataset `PredictionOutcomeRow`
    evaluation (`app.forecasting.accuracy_service`) reads "actual price
    on target_date" from -- distinct from `CacheEntryRow` (TTL cache)
    and `RawResearchDataRow` (one-off per-run capture), neither of which
    is meant to persist indefinitely."""

    __tablename__ = "daily_price_history"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_daily_price_history_ticker_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    date: Mapped[date_type] = mapped_column(Date, index=True, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    dma50: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    dma200: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    delivery_percentage: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # screener_import | yfinance_daily
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class AppSettingRow(Base):
    """A tiny runtime-editable key/value settings store, for the one
    setting that genuinely needs to change without a server restart:
    the Screener.in session cookie (`app.core.runtime_settings`). Not a
    general config system -- `app.core.config.Settings` (env vars) stays
    the source of truth for everything else. A row here, when present,
    takes precedence over the matching env var for that one key."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
