"""Generic TTL cache abstraction backed by the app's own SQL database.

Kept behind a small `CacheStore` interface so a future Redis-backed
implementation can be swapped in without touching any caller --
`SqlCacheStore` is the only implementation today, deliberately: the
project's existing SQLite/Postgres database already runs in every
environment this app runs in, so a first caching pass needs no new
infrastructure.

An expired row is returned as an expired `CacheHit`, not `None` --
callers that want stale-while-revalidate / provider-failure fallback
behavior can still read the last-known value; callers that just want a
plain cache check `CacheHit.is_expired` themselves.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sql_delete
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import CacheEntryRow

logger = logging.getLogger(__name__)


def _as_utc(value: datetime) -> datetime:
    """SQLite (used locally and in tests) round-trips `DateTime(timezone=True)`
    columns as naive datetimes -- Postgres preserves the timezone. Normalize
    to aware-UTC here so comparisons work the same on both backends."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class CacheHit:
    value: str
    cached_at: datetime
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


class CacheStore(ABC):
    @abstractmethod
    async def get(self, key: str) -> CacheHit | None: ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...


class SqlCacheStore(CacheStore):
    """Reads use the caller's session; writes use a short-lived session of
    their own on the same engine.

    Writing on the caller's session was unsafe twice over: `set()` issued
    a `commit()` on the request's transaction, and a failed cache write
    left that session needing a rollback, so the next unrelated `add()`
    raised `PendingRollbackError`. A cache failure is a cache failure --
    it must never become a research failure.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        # `session.bind` is the AsyncEngine; `get_bind()` would hand back
        # the sync engine underneath it, which async_sessionmaker rejects.
        self._write_session_factory = async_sessionmaker(
            bind=session.bind, expire_on_commit=False
        )

    async def get(self, key: str) -> CacheHit | None:
        row = await self._session.get(CacheEntryRow, key)
        if row is None:
            return None
        return CacheHit(value=row.value, cached_at=_as_utc(row.cached_at), expires_at=_as_utc(row.expires_at))

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Atomic upsert — concurrent writers of the same key must not
        collide on the primary key. Never raises: a cache write that
        fails is logged and dropped."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        try:
            async with self._write_session_factory() as write_session:
                dialect = write_session.bind.dialect.name
                insert = postgresql_insert if dialect == "postgresql" else sqlite_insert
                statement = insert(CacheEntryRow).values(
                    key=key, value=value, cached_at=now, expires_at=expires_at
                )
                await write_session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[CacheEntryRow.key],
                        set_={"value": value, "cached_at": now, "expires_at": expires_at},
                    )
                )
                await write_session.commit()
        except Exception:
            logger.warning("cache_write_failed key=%s", key, exc_info=True)

    async def delete(self, key: str) -> None:
        try:
            async with self._write_session_factory() as write_session:
                await write_session.execute(
                    sql_delete(CacheEntryRow).where(CacheEntryRow.key == key)
                )
                await write_session.commit()
        except Exception:
            logger.warning("cache_delete_failed key=%s", key, exc_info=True)
