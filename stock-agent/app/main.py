"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.analyst import router as analyst_router
from app.api.analyze import router as analyze_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.market import router as market_router
from app.api.portfolio import router as portfolio_router
from app.api.qa import router as qa_router
from app.api.research import router as research_router
from app.api.search import router as search_router
from app.api.sectors import router as sectors_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.db.base import create_all_tables, get_session_factory, init_engine
from app.scheduler.scheduler import start_scheduler, stop_scheduler

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine(settings.database_url)
    await create_all_tables()
    scheduler = start_scheduler(get_session_factory(), settings)
    try:
        yield
    finally:
        stop_scheduler(scheduler)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health_router)
app.include_router(analyst_router)
app.include_router(analyze_router)
app.include_router(auth_router)
app.include_router(market_router)
app.include_router(portfolio_router)
app.include_router(qa_router)
app.include_router(research_router)
app.include_router(search_router)
app.include_router(sectors_router)
