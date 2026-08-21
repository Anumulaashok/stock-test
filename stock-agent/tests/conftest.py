from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db import models  # noqa: F401 -- registers table metadata on Base
from app.db.base import Base, get_db
from app.main import app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        llm_provider="local",
        local_llm_base_url="http://test-llm-server:8080/v1",
        local_llm_model="test-model",
        database_url="postgresql+psycopg://user:pass@localhost:5432/db",
    )


@pytest.fixture
def db_client():
    """A `TestClient` backed by a fresh in-memory SQLite database, fully
    isolated from the app's configured `DATABASE_URL` (real Postgres in
    dev/prod) via a `get_db` dependency override -- no lifespan/startup
    DB connection is ever attempted in tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    tables_ready = False

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        # Created lazily, inside the request's own event loop (the
        # TestClient's blocking portal) rather than a separate
        # asyncio.run() loop -- aiosqlite connections are bound to the
        # loop that opened them.
        nonlocal tables_ready
        if not tables_ready:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            tables_ready = True
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
