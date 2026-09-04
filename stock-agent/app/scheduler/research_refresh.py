"""Twice-daily research refresh -- market open (09:30 IST) and close
(15:00 IST), recomputing every ticker that has ever been successfully
researched.

A NORMAL research request reuses today's already-completed snapshot for
the rest of the calendar day (see `app/snapshot/service.py`'s
`_find_reusable_run` -- deliberately, since a full recompute is
expensive: provider calls plus up to a ~2 minute LLM call). That means
without something actively forcing a recompute, a ticker researched
once in the morning shows the same financial analysis, valuation,
scoring, and forecast all day, with only the live quote refreshed on
top (`_overlay_fresh_quote`). This module is that active trigger: at
each scheduled time, force_refresh=True for every previously-researched
ticker, exactly what "Force Refresh" already does one ticker at a time
from the UI, batched and put on a schedule.

Coverage is every ticker with at least one COMPLETED/PARTIAL run ever
(not scoped to any watchlist) -- costs grow as more tickers get
researched over time; that tradeoff was chosen explicitly over a
cheaper watchlist-only scope.
"""

import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import build_research_snapshot_service
from app.core.config import Settings
from app.data.factory import get_financial_data_provider
from app.db.models import ResearchRunRow
from app.models.research_run import ResearchRunRequest, ResearchRunStatus
from app.snapshot.exceptions import ResearchInProgressError

logger = logging.getLogger(__name__)

# A ticker that hasn't been successfully researched in this long is
# treated as abandoned -- refreshing it forever, on a fixed schedule,
# regardless of whether anyone still looks at it would only grow the
# job's cost without bound. A viewer can always bring it back with an
# explicit Force Refresh, which re-enters the refreshed set on its own.
_STALE_CUTOFF_DAYS = 30


async def _tickers_due_for_refresh(db: AsyncSession, *, as_of: date) -> list[str]:
    cutoff = as_of - timedelta(days=_STALE_CUTOFF_DAYS)
    stmt = (
        select(ResearchRunRow.ticker)
        .where(
            ResearchRunRow.status.in_([ResearchRunStatus.COMPLETED.value, ResearchRunStatus.PARTIAL.value]),
            ResearchRunRow.research_date >= cutoff,
        )
        .distinct()
    )
    rows = (await db.execute(stmt)).scalars().all()
    return sorted(set(rows))


async def _refresh_one(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, ticker: str
) -> None:
    async with session_factory() as db:
        try:
            service = build_research_snapshot_service(settings, db)
            await service.run_research(
                db, ResearchRunRequest(ticker=ticker, force_refresh=True, include_price_trend_forecast=True)
            )
            logger.info("scheduled_research_refresh_completed ticker=%s", ticker)
        except ResearchInProgressError:
            # Someone (a user's own Force Refresh, or an overlapping
            # scheduled run) is already recomputing this ticker right
            # now -- their result is just as fresh; skip, don't queue a
            # redundant duplicate.
            logger.info("scheduled_research_refresh_skipped_in_progress ticker=%s", ticker)
        except Exception:
            # One ticker's provider/LLM failure must never abort the
            # rest of the batch.
            logger.warning("scheduled_research_refresh_failed ticker=%s", ticker, exc_info=True)


async def refresh_all_researched_tickers(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    """Entry point for the scheduled job. Bounds concurrency at
    `settings.research_auto_refresh_max_concurrency` -- each refresh is
    a full research run, so unbounded concurrency across many tickers
    would hammer the configured providers and the LLM endpoint all at
    once."""
    try:
        get_financial_data_provider(settings)
    except ValueError as exc:
        logger.info("scheduled_research_refresh_skipped_unconfigured error=%s", exc)
        return

    async with session_factory() as db:
        tickers = await _tickers_due_for_refresh(db, as_of=date.today())

    if not tickers:
        logger.info("scheduled_research_refresh_nothing_to_do")
        return

    logger.info("scheduled_research_refresh_started ticker_count=%d", len(tickers))
    semaphore = asyncio.Semaphore(max(1, settings.research_auto_refresh_max_concurrency))

    async def _bounded(ticker: str) -> None:
        async with semaphore:
            await _refresh_one(session_factory, settings, ticker)

    await asyncio.gather(*(_bounded(t) for t in tickers))
    logger.info("scheduled_research_refresh_finished ticker_count=%d", len(tickers))
