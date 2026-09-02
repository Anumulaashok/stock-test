from datetime import datetime, timedelta, timezone

import pytest

from app.cache.market_data import CachedMarketDataService
from app.cache.store import CacheHit, CacheStore
from app.models.market import (
    MarketDataError,
    MarketDataErrorCode,
    MarketQuote,
    MarketSnapshot,
    MarketSnapshotResult,
    MarketStatus,
    PriceFreshness,
)


class _InMemoryCacheStore(CacheStore):
    def __init__(self):
        self._entries: dict[str, CacheHit] = {}

    async def get(self, key):
        return self._entries.get(key)

    async def set(self, key, value, ttl_seconds):
        now = datetime.now(timezone.utc)
        self._entries[key] = CacheHit(value=value, cached_at=now, expires_at=now + timedelta(seconds=ttl_seconds))

    async def delete(self, key):
        self._entries.pop(key, None)

    def force_expire(self, key: str) -> None:
        hit = self._entries[key]
        self._entries[key] = CacheHit(
            value=hit.value, cached_at=hit.cached_at, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )


class _FakeMarketDataService:
    def __init__(self, result: MarketSnapshotResult):
        self.result = result
        self.calls: list[tuple[str, bool]] = []

    async def get_snapshot(self, ticker: str, include_recent_prices: bool = True) -> MarketSnapshotResult:
        self.calls.append((ticker, include_recent_prices))
        return self.result


def _quote(ticker="AAPL") -> MarketQuote:
    return MarketQuote(
        ticker=ticker, current_price=100, previous_close=99, change=1, change_percent=1.01,
        currency="USD", market_status=MarketStatus.OPEN, market_timestamp=None,
        data_timestamp="2026-08-21T00:00:00+00:00", freshness=PriceFreshness.LIVE, source="stub",
    )


def _success_result(ticker="AAPL") -> MarketSnapshotResult:
    return MarketSnapshotResult(
        status="success",
        snapshot=MarketSnapshot(ticker=ticker, quote=_quote(ticker), recent_prices=[], fetched_at="2026-08-21T00:00:00Z"),
    )


def _error_result() -> MarketSnapshotResult:
    return MarketSnapshotResult(
        status="error", error=MarketDataError(code=MarketDataErrorCode.PROVIDER_UNAVAILABLE, message="down")
    )


@pytest.mark.asyncio
async def test_cache_miss_fetches_from_inner():
    inner = _FakeMarketDataService(_success_result())
    cache = _InMemoryCacheStore()
    svc = CachedMarketDataService(inner, cache, provider_name="fmp", ttl_seconds=30)

    result = await svc.get_snapshot("AAPL")

    assert result.status == "success"
    assert inner.calls == [("AAPL", True)]


@pytest.mark.asyncio
async def test_cache_hit_never_calls_inner():
    inner = _FakeMarketDataService(_success_result())
    cache = _InMemoryCacheStore()
    svc = CachedMarketDataService(inner, cache, provider_name="fmp", ttl_seconds=30)

    await svc.get_snapshot("AAPL")
    await svc.get_snapshot("AAPL")

    assert inner.calls == [("AAPL", True)]


@pytest.mark.asyncio
async def test_ttl_expiry_refetches():
    inner = _FakeMarketDataService(_success_result())
    cache = _InMemoryCacheStore()
    svc = CachedMarketDataService(inner, cache, provider_name="fmp", ttl_seconds=30)

    await svc.get_snapshot("AAPL")
    cache.force_expire(svc._key("AAPL", True))
    await svc.get_snapshot("AAPL")

    assert inner.calls == [("AAPL", True), ("AAPL", True)]


@pytest.mark.asyncio
async def test_include_recent_prices_flag_is_part_of_the_cache_key():
    inner = _FakeMarketDataService(_success_result())
    cache = _InMemoryCacheStore()
    svc = CachedMarketDataService(inner, cache, provider_name="fmp", ttl_seconds=30)

    await svc.get_snapshot("AAPL", include_recent_prices=False)
    await svc.get_snapshot("AAPL", include_recent_prices=True)

    assert inner.calls == [("AAPL", False), ("AAPL", True)]


@pytest.mark.asyncio
async def test_get_quote_delegates_to_snapshot_without_recent_prices():
    inner = _FakeMarketDataService(_success_result())
    cache = _InMemoryCacheStore()
    svc = CachedMarketDataService(inner, cache, provider_name="fmp", ttl_seconds=30)

    await svc.get_quote("AAPL")

    assert inner.calls == [("AAPL", False)]


@pytest.mark.asyncio
async def test_provider_failure_with_cached_data_serves_stale_snapshot():
    cache = _InMemoryCacheStore()
    warm_inner = _FakeMarketDataService(_success_result())
    svc = CachedMarketDataService(warm_inner, cache, provider_name="fmp", ttl_seconds=30)
    await svc.get_snapshot("AAPL")
    cache.force_expire(svc._key("AAPL", True))

    failing_inner = _FakeMarketDataService(_error_result())
    svc_after_outage = CachedMarketDataService(failing_inner, cache, provider_name="fmp", ttl_seconds=30)
    result = await svc_after_outage.get_snapshot("AAPL")

    assert result.status == "success"
    assert result.snapshot.ticker == "AAPL"


@pytest.mark.asyncio
async def test_provider_failure_with_no_cached_data_returns_the_error():
    cache = _InMemoryCacheStore()
    inner = _FakeMarketDataService(_error_result())
    svc = CachedMarketDataService(inner, cache, provider_name="fmp", ttl_seconds=30)

    result = await svc.get_snapshot("AAPL")

    assert result.status == "error"
