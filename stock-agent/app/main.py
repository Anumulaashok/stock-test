"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.analyst import router as analyst_router
from app.api.analyze import router as analyze_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(analyst_router)
app.include_router(analyze_router)
