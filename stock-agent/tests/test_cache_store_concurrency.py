"""A cache failure must stay a cache failure.

The old store did `get()` then `insert()` on the caller's session and
committed it, so concurrent writers of the same key raced on the primary
key, and a failed write left the request's session needing a rollback --
turning a cache problem into a research problem at the next unrelated
`add()`.
"""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.cache.store import SqlCacheStore
from app.db.base import Base
from app.db.models import CacheEntryRow, ScreenerCompanyMappingRow


@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


async def test_concurrent_writes_of_the_same_key_do_not_collide(engine, session):
    """Twenty writers, one key: the old get-then-insert pattern raced
    here; an upsert must leave exactly one row and raise nothing."""
    store = SqlCacheStore(session)

    await asyncio.gather(*(store.set("financials:v1:indianapi:RECLTD", f"payload-{i}", 60) for i in range(20)))

    hit = await store.get("financials:v1:indianapi:RECLTD")
    assert hit is not None
    assert hit.value.startswith("payload-")

    rows = (await session.execute(CacheEntryRow.__table__.select())).all()
    assert len(rows) == 1


async def test_concurrent_writes_of_distinct_keys_all_land(engine, session):
    store = SqlCacheStore(session)
    await asyncio.gather(*(store.set(f"key-{i}", f"value-{i}", 60) for i in range(10)))
    for i in range(10):
        hit = await store.get(f"key-{i}")
        assert hit is not None and hit.value == f"value-{i}"


async def test_repeated_set_overwrites_rather_than_duplicating(engine, session):
    store = SqlCacheStore(session)
    await store.set("k", "first", 60)
    await store.set("k", "second", 60)
    hit = await store.get("k")
    assert hit.value == "second"


async def test_caching_does_not_commit_the_callers_pending_work(engine, session):
    """The store used to call `commit()` on the request's session, which
    silently committed whatever else that session had pending. Caching a
    value must not decide when unrelated work becomes durable."""
    store = SqlCacheStore(session)

    session.add(ScreenerCompanyMappingRow(ticker="RECLTD", company_name="REC", screener_company_id=1))
    await store.set("financials:v1:indianapi:RECLTD", "payload", 60)
    await session.rollback()

    assert await session.get(ScreenerCompanyMappingRow, "RECLTD") is None
    # The cached value itself was committed on its own session and survives.
    assert (await store.get("financials:v1:indianapi:RECLTD")).value == "payload"


async def test_failing_cache_write_is_swallowed_and_leaves_the_caller_usable(engine, session, monkeypatch):
    """A cache failure must be a CACHE_FAILURE, never a research failure."""
    store = SqlCacheStore(session)

    def _explode(*args, **kwargs):
        raise RuntimeError("database is unavailable")

    monkeypatch.setattr(store, "_write_session_factory", _explode)

    session.add(ScreenerCompanyMappingRow(ticker="RECLTD", company_name="REC", screener_company_id=1))
    await store.set("k", "value", 60)  # must not raise
    await store.delete("k")  # nor must this

    # The request's own transaction is untouched and still commits.
    session.add(ScreenerCompanyMappingRow(ticker="HUDCO", company_name="HUDCO", screener_company_id=2))
    await session.commit()

    assert await session.get(ScreenerCompanyMappingRow, "RECLTD") is not None
    assert await session.get(ScreenerCompanyMappingRow, "HUDCO") is not None


async def test_deleting_a_missing_key_is_a_no_op(engine, session):
    store = SqlCacheStore(session)
    await store.delete("never-existed")
    session.add(ScreenerCompanyMappingRow(ticker="PFC", company_name="PFC", screener_company_id=3))
    await session.commit()
    assert await session.get(ScreenerCompanyMappingRow, "PFC") is not None


async def test_delete_removes_the_entry(engine, session):
    store = SqlCacheStore(session)
    await store.set("k", "v", 60)
    await store.delete("k")
    assert await store.get("k") is None
