import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.cache.store import SqlCacheStore
from app.db.base import Base
from app.db import models  # noqa: F401 -- registers table metadata on Base


@pytest.fixture
async def store():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield SqlCacheStore(session)


@pytest.mark.asyncio
async def test_miss_returns_none(store):
    assert await store.get("missing-key") is None


@pytest.mark.asyncio
async def test_set_then_get_returns_value(store):
    await store.set("k1", "hello", ttl_seconds=60)
    hit = await store.get("k1")
    assert hit is not None
    assert hit.value == "hello"
    assert not hit.is_expired


@pytest.mark.asyncio
async def test_expired_entry_is_returned_but_flagged_expired(store):
    await store.set("k1", "stale-value", ttl_seconds=-1)
    hit = await store.get("k1")
    assert hit is not None
    assert hit.value == "stale-value"
    assert hit.is_expired


@pytest.mark.asyncio
async def test_set_overwrites_existing_key(store):
    await store.set("k1", "first", ttl_seconds=60)
    await store.set("k1", "second", ttl_seconds=60)
    hit = await store.get("k1")
    assert hit.value == "second"


@pytest.mark.asyncio
async def test_delete_removes_entry(store):
    await store.set("k1", "value", ttl_seconds=60)
    await store.delete("k1")
    assert await store.get("k1") is None


@pytest.mark.asyncio
async def test_delete_missing_key_is_a_no_op(store):
    await store.delete("never-existed")
