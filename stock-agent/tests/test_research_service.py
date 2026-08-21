from datetime import datetime, timezone

import pytest

from app.models.research import ResearchErrorCode, ResearchItem, ResearchQuery, ResearchSource
from app.research.base import ResearchProvider
from app.research.exceptions import ResearchProviderError
from app.research.service import ResearchService


def _item(id="i1", url="https://a.com/1", title="Acme Corp news", published_at="2026-01-01T00:00:00+00:00"):
    return ResearchItem(
        id=id, title=title,
        source=ResearchSource(title=title, publisher="News Co", url=url, published_at=published_at),
        published_at=published_at,
    )


class FakeProvider(ResearchProvider):
    def __init__(self, items=None, warnings=None, raises=None):
        self._items = items or []
        self._warnings = warnings or []
        self._raises = raises
        self.calls = []

    async def search(self, query):
        self.calls.append(query)
        if self._raises:
            raise self._raises
        return self._items, self._warnings


def _fixed_clock():
    return datetime(2026, 1, 10, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_search_deterministic_query_reaches_provider_unchanged():
    provider = FakeProvider(items=[_item()])
    service = ResearchService(provider, clock=_fixed_clock)
    query = ResearchQuery(company_name="Acme Corp", ticker="ACME")

    await service.search(query)

    assert provider.calls[0].company_name == "Acme Corp"
    assert provider.calls[0].ticker == "ACME"


@pytest.mark.asyncio
async def test_search_success_returns_scored_items():
    provider = FakeProvider(items=[_item()])
    service = ResearchService(provider, clock=_fixed_clock)

    result = await service.search(ResearchQuery(company_name="Acme Corp", ticker="ACME"))

    assert result.status == "success"
    assert len(result.items) == 1
    assert result.items[0].id == "research_001"
    assert result.items[0].relevance is not None
    assert result.items[0].freshness.value == "recent"


@pytest.mark.asyncio
async def test_search_deduplicates_before_returning():
    provider = FakeProvider(items=[_item(url="https://a.com/1"), _item(url="https://a.com/1")])
    service = ResearchService(provider, clock=_fixed_clock)

    result = await service.search(ResearchQuery(company_name="Acme Corp"))

    assert len(result.items) == 1
    assert any("duplicate" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_search_respects_max_results():
    items = [_item(id=f"i{n}", url=f"https://a.com/{n}", title=f"Headline {n}") for n in range(10)]
    provider = FakeProvider(items=items)
    service = ResearchService(provider, default_max_results=5, clock=_fixed_clock)

    result = await service.search(ResearchQuery(company_name="Acme Corp"))

    assert len(result.items) == 5


@pytest.mark.asyncio
async def test_search_query_max_results_overrides_default():
    items = [_item(id=f"i{n}", url=f"https://a.com/{n}", title=f"Headline {n}") for n in range(10)]
    provider = FakeProvider(items=items)
    service = ResearchService(provider, default_max_results=5, clock=_fixed_clock)

    result = await service.search(ResearchQuery(company_name="Acme Corp", max_results=2))

    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_search_no_results_is_success_with_warning():
    provider = FakeProvider(items=[])
    service = ResearchService(provider, clock=_fixed_clock)

    result = await service.search(ResearchQuery(company_name="Acme Corp"))

    assert result.status == "success"
    assert result.items == []
    assert any("no relevant research results" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_search_provider_warnings_propagate():
    provider = FakeProvider(items=[_item()], warnings=["skipped an article with no headline"])
    service = ResearchService(provider, clock=_fixed_clock)

    result = await service.search(ResearchQuery(company_name="Acme Corp"))

    assert "skipped an article with no headline" in result.warnings


@pytest.mark.asyncio
async def test_search_provider_failure_returns_structured_error():
    provider = FakeProvider(raises=ResearchProviderError(ResearchErrorCode.PROVIDER_UNAVAILABLE, "down"))
    service = ResearchService(provider, clock=_fixed_clock)

    result = await service.search(ResearchQuery(company_name="Acme Corp"))

    assert result.status == "error"
    assert result.error.code is ResearchErrorCode.PROVIDER_UNAVAILABLE
    assert result.items == []


@pytest.mark.asyncio
async def test_search_invalid_query_without_company_or_ticker():
    provider = FakeProvider()
    service = ResearchService(provider, clock=_fixed_clock)

    result = await service.search(ResearchQuery(company_name=""))

    assert result.status == "error"
    assert result.error.code is ResearchErrorCode.INVALID_QUERY
    assert provider.calls == []


@pytest.mark.asyncio
async def test_search_stale_items_marked_stale_not_recent():
    old_item = _item(published_at="2020-01-01T00:00:00+00:00")
    provider = FakeProvider(items=[old_item])
    service = ResearchService(provider, stale_after_days=14, clock=_fixed_clock)

    result = await service.search(ResearchQuery(company_name="Acme Corp"))

    assert result.items[0].freshness.value == "stale"
