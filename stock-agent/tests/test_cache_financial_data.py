import pytest

from app.cache.financial_data import CachedFinancialDataService
from app.cache.store import CacheStore, CacheHit
from app.data.models import (
    CompanyIdentifier,
    FinancialDataError,
    FinancialDataErrorCode,
    FinancialDataFetchResult,
    FinancialDataMetadata,
    FinancialDataResult,
)
from app.data.service import FinancialDataService
from app.models.financial_statements import CompanyFinancials


class _InMemoryCacheStore(CacheStore):
    """A trivial in-process CacheStore for testing the wrapper's cache
    logic in isolation from `SqlCacheStore`/the DB (that's covered by
    tests/test_cache_store.py)."""

    def __init__(self):
        self._entries: dict[str, CacheHit] = {}

    async def get(self, key):
        return self._entries.get(key)

    async def set(self, key, value, ttl_seconds):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        self._entries[key] = CacheHit(value=value, cached_at=now, expires_at=now + timedelta(seconds=ttl_seconds))

    async def delete(self, key):
        self._entries.pop(key, None)

    def force_expire(self, key: str) -> None:
        from datetime import datetime, timedelta, timezone

        hit = self._entries[key]
        self._entries[key] = CacheHit(
            value=hit.value, cached_at=hit.cached_at, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )


class _FakeFinancialDataService:
    def __init__(self, result: FinancialDataFetchResult):
        self.result = result
        self.calls: list[str] = []

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataFetchResult:
        self.calls.append(identifier.ticker)
        return self.result


def _success_result(ticker="ACME") -> FinancialDataFetchResult:
    return FinancialDataFetchResult(
        status="success",
        data=FinancialDataResult(
            company_financials=CompanyFinancials(company_name=ticker, ticker=ticker),
            metadata=FinancialDataMetadata(
                provider="fmp", source_identifier=ticker, retrieved_at="2026-01-01T00:00:00Z"
            ),
            warnings=[],
        ),
    )


def _error_result() -> FinancialDataFetchResult:
    return FinancialDataFetchResult(
        status="error",
        error=FinancialDataError(code=FinancialDataErrorCode.PROVIDER_UNAVAILABLE, message="down"),
    )


@pytest.mark.asyncio
async def test_cache_miss_fetches_from_inner_and_populates_cache():
    inner = _FakeFinancialDataService(_success_result())
    cache = _InMemoryCacheStore()
    svc = CachedFinancialDataService(inner, cache, provider_name="fmp", ttl_seconds=60)

    result = await svc.get_company_financials(CompanyIdentifier(ticker="ACME"))

    assert result.status == "success"
    assert inner.calls == ["ACME"]
    assert await cache.get(svc._key("ACME")) is not None


@pytest.mark.asyncio
async def test_cache_hit_never_calls_inner():
    inner = _FakeFinancialDataService(_success_result())
    cache = _InMemoryCacheStore()
    svc = CachedFinancialDataService(inner, cache, provider_name="fmp", ttl_seconds=60)

    first = await svc.get_company_financials(CompanyIdentifier(ticker="ACME"))
    second = await svc.get_company_financials(CompanyIdentifier(ticker="ACME"))

    assert inner.calls == ["ACME"]  # only the first call reached the provider
    assert second.data.company_financials.ticker == first.data.company_financials.ticker


@pytest.mark.asyncio
async def test_ttl_expiry_refetches_from_inner():
    inner = _FakeFinancialDataService(_success_result())
    cache = _InMemoryCacheStore()
    svc = CachedFinancialDataService(inner, cache, provider_name="fmp", ttl_seconds=60)

    await svc.get_company_financials(CompanyIdentifier(ticker="ACME"))
    cache.force_expire(svc._key("ACME"))
    await svc.get_company_financials(CompanyIdentifier(ticker="ACME"))

    assert inner.calls == ["ACME", "ACME"]


@pytest.mark.asyncio
async def test_cache_key_is_scoped_per_provider():
    inner = _FakeFinancialDataService(_success_result())
    cache = _InMemoryCacheStore()
    fmp_svc = CachedFinancialDataService(inner, cache, provider_name="fmp", ttl_seconds=60)
    indianapi_svc = CachedFinancialDataService(inner, cache, provider_name="indianapi", ttl_seconds=60)

    await fmp_svc.get_company_financials(CompanyIdentifier(ticker="ACME"))
    await indianapi_svc.get_company_financials(CompanyIdentifier(ticker="ACME"))

    assert inner.calls == ["ACME", "ACME"]  # each provider's cache is independent


@pytest.mark.asyncio
async def test_provider_failure_with_cached_data_serves_stale_cache():
    cache = _InMemoryCacheStore()
    warm_inner = _FakeFinancialDataService(_success_result())
    svc = CachedFinancialDataService(warm_inner, cache, provider_name="fmp", ttl_seconds=60)
    await svc.get_company_financials(CompanyIdentifier(ticker="ACME"))
    cache.force_expire(svc._key("ACME"))

    failing_inner = _FakeFinancialDataService(_error_result())
    svc_after_outage = CachedFinancialDataService(failing_inner, cache, provider_name="fmp", ttl_seconds=60)
    result = await svc_after_outage.get_company_financials(CompanyIdentifier(ticker="ACME"))

    assert result.status == "success"  # served from the stale cache entry, not the failing provider
    assert result.data.company_financials.ticker == "ACME"


@pytest.mark.asyncio
async def test_provider_failure_with_no_cached_data_returns_the_error():
    cache = _InMemoryCacheStore()
    inner = _FakeFinancialDataService(_error_result())
    svc = CachedFinancialDataService(inner, cache, provider_name="fmp", ttl_seconds=60)

    result = await svc.get_company_financials(CompanyIdentifier(ticker="ACME"))

    assert result.status == "error"


@pytest.mark.asyncio
async def test_wraps_real_financial_data_service_end_to_end():
    from app.data.base import FinancialDataProvider

    class _RealProvider(FinancialDataProvider):
        def __init__(self):
            self.calls = 0

        async def get_company_financials(self, identifier: CompanyIdentifier):
            self.calls += 1
            return _success_result(identifier.ticker).data

    provider = _RealProvider()
    cache = _InMemoryCacheStore()
    svc = CachedFinancialDataService(FinancialDataService(provider), cache, provider_name="fmp", ttl_seconds=60)

    await svc.get_company_financials(CompanyIdentifier(ticker="ACME"))
    await svc.get_company_financials(CompanyIdentifier(ticker="ACME"))

    assert provider.calls == 1


# --- negative caching: a failure gets cached too, briefly ---------------------------


@pytest.mark.asyncio
async def test_failure_is_cached_under_the_negative_ttl():
    inner = _FakeFinancialDataService(_error_result())
    cache = _InMemoryCacheStore()
    svc = CachedFinancialDataService(inner, cache, provider_name="fmp", ttl_seconds=60, negative_ttl_seconds=120)

    await svc.get_company_financials(CompanyIdentifier(ticker="HUDCO"))

    hit = await cache.get(svc._key("HUDCO"))
    assert hit is not None
    ttl = (hit.expires_at - hit.cached_at).total_seconds()
    assert 119 <= ttl <= 121


@pytest.mark.asyncio
async def test_repeated_requests_within_negative_ttl_do_not_hit_provider_again():
    inner = _FakeFinancialDataService(_error_result())
    cache = _InMemoryCacheStore()
    svc = CachedFinancialDataService(inner, cache, provider_name="fmp", ttl_seconds=60, negative_ttl_seconds=120)

    first = await svc.get_company_financials(CompanyIdentifier(ticker="HUDCO"))
    second = await svc.get_company_financials(CompanyIdentifier(ticker="HUDCO"))

    assert first.status == "error"
    assert second.status == "error"
    assert inner.calls == ["HUDCO"]  # second request served from the negative cache


@pytest.mark.asyncio
async def test_negative_cache_expiry_refetches_from_inner():
    inner = _FakeFinancialDataService(_error_result())
    cache = _InMemoryCacheStore()
    svc = CachedFinancialDataService(inner, cache, provider_name="fmp", ttl_seconds=60, negative_ttl_seconds=120)

    await svc.get_company_financials(CompanyIdentifier(ticker="HUDCO"))
    cache.force_expire(svc._key("HUDCO"))
    await svc.get_company_financials(CompanyIdentifier(ticker="HUDCO"))

    assert inner.calls == ["HUDCO", "HUDCO"]


@pytest.mark.asyncio
async def test_negative_cache_default_ttl_is_short_not_seven_days():
    inner = _FakeFinancialDataService(_error_result())
    cache = _InMemoryCacheStore()
    svc = CachedFinancialDataService(inner, cache, provider_name="fmp", ttl_seconds=60)  # default negative TTL

    await svc.get_company_financials(CompanyIdentifier(ticker="HUDCO"))

    hit = await cache.get(svc._key("HUDCO"))
    ttl = (hit.expires_at - hit.cached_at).total_seconds()
    assert ttl <= 300  # minutes, not the 7-day success TTL


@pytest.mark.asyncio
async def test_success_after_a_cached_failure_overwrites_it_with_the_long_ttl():
    cache = _InMemoryCacheStore()
    failing_svc = CachedFinancialDataService(
        _FakeFinancialDataService(_error_result()), cache, provider_name="fmp", ttl_seconds=60, negative_ttl_seconds=120
    )
    await failing_svc.get_company_financials(CompanyIdentifier(ticker="HUDCO"))
    cache.force_expire(failing_svc._key("HUDCO"))  # simulate the negative-cache window elapsing

    recovered_svc = CachedFinancialDataService(
        _FakeFinancialDataService(_success_result("HUDCO")), cache, provider_name="fmp", ttl_seconds=60
    )
    result = await recovered_svc.get_company_financials(CompanyIdentifier(ticker="HUDCO"))

    assert result.status == "success"
    hit = await cache.get(failing_svc._key("HUDCO"))
    ttl = (hit.expires_at - hit.cached_at).total_seconds()
    assert 59 <= ttl <= 61  # now cached under the success TTL, not the negative one
