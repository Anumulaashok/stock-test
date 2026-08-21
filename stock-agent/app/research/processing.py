"""Provider-agnostic research post-processing: deduplication, freshness
tagging, deterministic relevance scoring, and ranking/truncation.

Pure functions only — no I/O, no LLM calls. Every provider's mapped
`ResearchItem`s pass through the same rules here, so behavior doesn't
vary by provider.
"""

from datetime import datetime, timezone
from decimal import Decimal

from app.models.research import ResearchFreshness, ResearchItem, ResearchQuery, ResearchSource

_BASE_RELEVANCE = Decimal("0.3")  # a ticker-scoped provider query already implies some relevance
_TICKER_MATCH_BONUS = Decimal("0.4")
_NAME_MATCH_BONUS = Decimal("0.3")
_MAX_RELEVANCE = Decimal("1.0")


def _normalize_title(title: str) -> str:
    return " ".join(title.lower().split())


def _normalize_url(url: str) -> str:
    return url.rstrip("/").lower()


def deduplicate(items: list[ResearchItem]) -> tuple[list[ResearchItem], list[str]]:
    """Remove duplicates by canonical URL, then by (title, publisher,
    published_at) among what's left — deterministic, no LLM involved."""
    warnings: list[str] = []
    seen_urls: set[str] = set()
    seen_signatures: set[tuple] = set()
    result: list[ResearchItem] = []

    for item in items:
        url_key = _normalize_url(item.source.url)
        if url_key in seen_urls:
            warnings.append(f"removed duplicate article (same URL): {item.title!r}")
            continue
        signature = (_normalize_title(item.title), item.source.publisher, item.published_at)
        if signature in seen_signatures:
            warnings.append(
                f"removed duplicate article (same title/publisher/date): {item.title!r}"
            )
            continue
        seen_urls.add(url_key)
        seen_signatures.add(signature)
        result.append(item)

    return result, warnings


def compute_freshness(
    published_at: str | None, retrieved_at: datetime, stale_after_days: int
) -> ResearchFreshness:
    """`recent` if published within `stale_after_days` of `retrieved_at`,
    `stale` if older, `unknown` if no usable publication date — an
    article is never presented as recent when its age can't be verified."""
    if published_at is None:
        return ResearchFreshness.UNKNOWN
    try:
        published = datetime.fromisoformat(published_at)
    except ValueError:
        return ResearchFreshness.UNKNOWN
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    age_days = (retrieved_at - published).days
    if age_days < 0:
        return ResearchFreshness.UNKNOWN  # future-dated: don't trust it
    return ResearchFreshness.RECENT if age_days <= stale_after_days else ResearchFreshness.STALE


def compute_relevance(item: ResearchItem, query: ResearchQuery) -> Decimal:
    """Deterministic relevance: base score for being returned by a
    ticker-scoped query, plus a bonus if the ticker or company name
    actually appears in the title/summary text. Never LLM-assigned."""
    haystack = f"{item.title} {item.summary or ''}".lower()
    score = _BASE_RELEVANCE
    if query.ticker and query.ticker.lower() in haystack:
        score += _TICKER_MATCH_BONUS
    if query.company_name.lower() in haystack:
        score += _NAME_MATCH_BONUS
    return min(score, _MAX_RELEVANCE)


def rank_and_limit(items: list[ResearchItem], max_results: int) -> list[ResearchItem]:
    """Highest relevance first, capped at `max_results` — keeps the
    context small and high-signal for the CPU-only analyst LLM call."""
    ranked = sorted(items, key=lambda i: i.relevance or Decimal(0), reverse=True)
    return ranked[:max_results]


def unique_sources(items: list[ResearchItem]) -> list[ResearchSource]:
    seen: set[str] = set()
    sources: list[ResearchSource] = []
    for item in items:
        key = _normalize_url(item.source.url)
        if key in seen:
            continue
        seen.add(key)
        sources.append(item.source)
    return sources
