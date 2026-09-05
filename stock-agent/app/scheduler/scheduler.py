"""Starts/stops the in-process job scheduler behind the twice-daily
research refresh (see `research_refresh.py`). No new infrastructure --
runs for the lifetime of the FastAPI process, wired into its lifespan.
Never blocks a request: `AsyncIOScheduler` schedules its jobs onto the
same asyncio event loop uvicorn already runs, as background tasks.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.scheduler.research_refresh import refresh_all_researched_tickers

logger = logging.getLogger(__name__)

_MARKET_TIMEZONE = "Asia/Kolkata"
# NSE/BSE trading hours are 09:15-15:30 IST. Times chosen to match: an
# initial pass shortly after the opening auction settles, and a second
# right before the closing auction, matching the "9:30 and 3 o'clock"
# schedule explicitly requested.
_MARKET_OPEN_TRIGGER = CronTrigger(hour=9, minute=30, timezone=_MARKET_TIMEZONE)
_MARKET_CLOSE_TRIGGER = CronTrigger(hour=15, minute=0, timezone=_MARKET_TIMEZONE)


def start_scheduler(session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> AsyncIOScheduler | None:
    if not settings.research_auto_refresh_enabled:
        logger.info("research_auto_refresh_disabled")
        return None

    scheduler = AsyncIOScheduler(timezone=_MARKET_TIMEZONE)

    async def _job() -> None:
        await refresh_all_researched_tickers(session_factory, settings)

    scheduler.add_job(
        _job, trigger=_MARKET_OPEN_TRIGGER, id="research_refresh_market_open",
        name="Research refresh (market open, 09:30 IST)", misfire_grace_time=1800, coalesce=True,
    )
    scheduler.add_job(
        _job, trigger=_MARKET_CLOSE_TRIGGER, id="research_refresh_market_close",
        name="Research refresh (market close, 15:00 IST)", misfire_grace_time=1800, coalesce=True,
    )
    scheduler.start()
    logger.info("research_auto_refresh_scheduler_started")
    return scheduler


def stop_scheduler(scheduler: AsyncIOScheduler | None) -> None:
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("research_auto_refresh_scheduler_stopped")
