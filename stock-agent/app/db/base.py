"""Async SQLAlchemy engine/session wiring.

Keeps persistence infrastructure separate from domain/service code —
services depend on an injected `AsyncSession` (via the `get_db` FastAPI
dependency), never on this module's engine directly. Defaults to a
local SQLite file so the app runs with zero external setup; a Postgres
URL (`postgresql+asyncpg://...`) works as a drop-in `DATABASE_URL`
override for production.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str) -> None:
    """Idempotent: safe to call once at app startup."""
    global _engine, _session_factory
    _engine = create_async_engine(database_url)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine not initialized — call init_engine() first")
    return _engine


async def create_all_tables() -> None:
    # Import models so their table metadata is registered on Base before
    # create_all runs — this module must not import app.db.models at
    # module scope to avoid a circular import (models imports Base).
    from app.db import models  # noqa: F401

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database engine not initialized — call init_engine() first")
    async with _session_factory() as session:
        yield session
