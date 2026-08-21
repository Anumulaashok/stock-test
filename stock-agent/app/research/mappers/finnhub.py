"""Maps Finnhub's company-news schema into `ResearchItem`.

Pure functions only — no HTTP. Verified against Finnhub's documented
response shape: `category`, `datetime` (Unix seconds), `headline`, `id`,
`image`, `related`, `source`, `summary`, `url`.

An article missing a headline or a valid http(s) URL is skipped
entirely — it can't be cited as evidence if it can't be traced back to
a source. A missing/invalid publication date does not cause the article
to be skipped, but leaves `published_at`/freshness unavailable rather
than inventing a date.
"""

from urllib.parse import urlparse

from app.models.research import ResearchItem, ResearchSource, SourceType

_ALLOWED_SCHEMES = {"http", "https"}


def _valid_url(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        return None
    return value


def _normalize_published_at(raw_datetime: object) -> str | None:
    if not isinstance(raw_datetime, (int, float)) or isinstance(raw_datetime, bool):
        return None
    if raw_datetime <= 0:
        return None
    from datetime import datetime, timezone

    try:
        return datetime.fromtimestamp(raw_datetime, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _source_type(category: object) -> SourceType:
    if isinstance(category, str) and category.strip().lower() == "company":
        return SourceType.COMPANY
    return SourceType.NEWS


def _clean_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def map_articles(raw_records: list[dict]) -> tuple[list[ResearchItem], list[str]]:
    """Maps raw Finnhub article dicts into `ResearchItem`s (unranked,
    undeduplicated — see `app.research.processing` for that).

    `ResearchItem.id` is set to a placeholder here; `ResearchService`
    assigns the final stable id after ranking/truncation so ids are
    sequential in the order actually presented to the analyst.
    """
    warnings: list[str] = []
    items: list[ResearchItem] = []

    for raw in raw_records:
        title = _clean_str(raw.get("headline"))
        if title is None:
            warnings.append("skipped an article with no headline")
            continue

        url = _valid_url(raw.get("url"))
        if url is None:
            warnings.append(f"skipped article {title!r}: missing or invalid URL")
            continue

        published_at = _normalize_published_at(raw.get("datetime"))
        if published_at is None:
            warnings.append(f"article {title!r} has no usable publication date")

        publisher = _clean_str(raw.get("source"))
        summary = _clean_str(raw.get("summary"))
        source_type = _source_type(raw.get("category"))

        source = ResearchSource(
            title=title, publisher=publisher, url=url,
            published_at=published_at, source_type=source_type,
        )
        items.append(
            ResearchItem(
                id="pending", title=title, summary=summary,
                source=source, published_at=published_at,
            )
        )

    return items, warnings
