from datetime import datetime, timezone
from decimal import Decimal

from app.models.research import ResearchFreshness, ResearchItem, ResearchQuery, ResearchSource
from app.research.processing import (
    compute_freshness,
    compute_relevance,
    deduplicate,
    rank_and_limit,
    unique_sources,
)


def d(value) -> Decimal:
    return Decimal(str(value))


def item(id="i1", title="Acme Corp expands", url="https://a.com/1", publisher="News Co",
         published_at="2026-01-01T00:00:00+00:00", summary=None):
    return ResearchItem(
        id=id, title=title, summary=summary,
        source=ResearchSource(title=title, publisher=publisher, url=url, published_at=published_at),
        published_at=published_at,
    )


# --- deduplicate ------------------------------------------------------------------


def test_dedupe_same_url_removed():
    items = [item(url="https://a.com/1"), item(url="https://a.com/1")]
    result, warnings = deduplicate(items)
    assert len(result) == 1
    assert any("same URL" in w for w in warnings)


def test_dedupe_url_case_and_trailing_slash_insensitive():
    items = [item(url="https://a.com/1"), item(url="HTTPS://A.COM/1/")]
    result, _ = deduplicate(items)
    assert len(result) == 1


def test_dedupe_same_title_publisher_date_different_url():
    items = [
        item(url="https://a.com/1", title="Same Title", publisher="News Co", published_at="2026-01-01T00:00:00+00:00"),
        item(url="https://b.com/1", title="Same Title", publisher="News Co", published_at="2026-01-01T00:00:00+00:00"),
    ]
    result, warnings = deduplicate(items)
    assert len(result) == 1
    assert any("same title/publisher/date" in w for w in warnings)


def test_dedupe_different_titles_not_removed():
    items = [item(url="https://a.com/1", title="A"), item(url="https://a.com/2", title="B")]
    result, warnings = deduplicate(items)
    assert len(result) == 2
    assert warnings == []


# --- freshness --------------------------------------------------------------------


def test_freshness_recent():
    retrieved_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
    published = "2026-01-05T00:00:00+00:00"
    assert compute_freshness(published, retrieved_at, stale_after_days=14) is ResearchFreshness.RECENT


def test_freshness_stale():
    retrieved_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    published = "2024-01-01T00:00:00+00:00"  # ~2 years old
    assert compute_freshness(published, retrieved_at, stale_after_days=14) is ResearchFreshness.STALE


def test_freshness_unknown_when_no_date():
    retrieved_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
    assert compute_freshness(None, retrieved_at, stale_after_days=14) is ResearchFreshness.UNKNOWN


def test_freshness_unknown_when_unparseable():
    retrieved_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
    assert compute_freshness("not-a-date", retrieved_at, stale_after_days=14) is ResearchFreshness.UNKNOWN


def test_freshness_unknown_when_future_dated():
    retrieved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert compute_freshness("2027-01-01T00:00:00+00:00", retrieved_at, stale_after_days=14) is ResearchFreshness.UNKNOWN


def test_freshness_boundary_exactly_at_threshold_is_recent():
    retrieved_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
    published = "2026-01-01T00:00:00+00:00"  # exactly 14 days
    assert compute_freshness(published, retrieved_at, stale_after_days=14) is ResearchFreshness.RECENT


# --- relevance --------------------------------------------------------------------


def test_relevance_ticker_and_name_match_maxes_out():
    query = ResearchQuery(company_name="Acme Corp", ticker="ACME")
    it = item(title="ACME (Acme Corp) announces expansion")
    assert compute_relevance(it, query) == d("1.0")


def test_relevance_base_score_when_no_match():
    query = ResearchQuery(company_name="Zeta Industries", ticker="ZETA")
    it = item(title="Unrelated headline", summary=None)
    assert compute_relevance(it, query) == d("0.3")


def test_relevance_ticker_match_only():
    query = ResearchQuery(company_name="Zeta Industries", ticker="ACME")
    it = item(title="ACME reports earnings")
    assert compute_relevance(it, query) == d("0.7")  # 0.3 base + 0.4 ticker


def test_relevance_capped_at_one():
    query = ResearchQuery(company_name="Acme Corp Acme Corp", ticker="ACME")
    it = item(title="ACME Acme Corp Acme Corp Acme Corp")
    assert compute_relevance(it, query) <= d("1.0")


# --- rank_and_limit -----------------------------------------------------------------


def test_rank_and_limit_orders_by_relevance_desc():
    low = item(id="low", url="https://a.com/1").model_copy(update={"relevance": d("0.3")})
    high = item(id="high", url="https://a.com/2").model_copy(update={"relevance": d("0.9")})
    ranked = rank_and_limit([low, high], max_results=10)
    assert [i.id for i in ranked] == ["high", "low"]


def test_rank_and_limit_truncates():
    items = [
        item(id=f"i{n}", url=f"https://a.com/{n}").model_copy(update={"relevance": d(str(n))})
        for n in range(10)
    ]
    ranked = rank_and_limit(items, max_results=3)
    assert len(ranked) == 3


# --- unique_sources -----------------------------------------------------------------


def test_unique_sources_dedupes_by_url():
    items = [item(url="https://a.com/1"), item(url="https://a.com/1"), item(url="https://a.com/2")]
    sources = unique_sources(items)
    assert len(sources) == 2
