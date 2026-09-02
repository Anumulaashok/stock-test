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

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CacheEntryRow


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
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> CacheHit | None:
        row = await self._session.get(CacheEntryRow, key)
        if row is None:
            return None
        return CacheHit(value=row.value, cached_at=_as_utc(row.cached_at), expires_at=_as_utc(row.expires_at))

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        row = await self._session.get(CacheEntryRow, key)
        if row is None:
            self._session.add(
                CacheEntryRow(key=key, value=value, cached_at=now, expires_at=expires_at)
            )
        else:
            row.value = value
            row.cached_at = now
            row.expires_at = expires_at
        await self._session.commit()

    async def delete(self, key: str) -> None:
        row = await self._session.get(CacheEntryRow, key)
        if row is not None:
            await self._session.delete(row)
            await self._session.commit()
