"""Turns raw `app.news.client.NewsClient` search results into classified,
timed `NewsEvent`s and persists them (spec section 8) -- this is how the
`news_events` table (see `app.db.models.NewsEventRow`) accumulates going
forward. There is no source of years of historical Indian-equity
headlines available to this project (see the implementation assessment),
so this is the only path new rows arrive by; the event-study/feature
code is otherwise written to work correctly once enough rows exist.
"""

import logging
from datetime import datetime, timezone

from dateutil import parser as date_parser

from app.news.client import NewsClient
from app.forecasting.ml.news.classifier import EventClassifier, KeywordEventClassifier
from app.forecasting.ml.news.models import NewsEvent
from app.forecasting.ml.news.novelty import compute_novelty_score
from app.forecasting.ml.news.timing import classify_market_timing

logger = logging.getLogger(__name__)


def _parse_published_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = date_parser.parse(raw)
    except (ValueError, OverflowError):
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


class NewsEventIngestionService:
    def __init__(self, news_client: NewsClient, classifier: EventClassifier | None = None) -> None:
        self._news_client = news_client
        self._classifier = classifier or KeywordEventClassifier()

    async def fetch_and_classify(
        self, *, ticker: str, company_name: str | None, recent_events: list[NewsEvent], limit: int = 10
    ) -> list[NewsEvent]:
        """`recent_events` should be this ticker's already-stored events
        (any lookback window is fine; only used for novelty scoring) so a
        re-fetch of an already-seen story scores low novelty instead of
        looking like new information every time this runs."""
        query = company_name or ticker
        result = await self._news_client.search(query, limit=limit)
        if result.status != "success":
            logger.info("news_ingestion_unavailable ticker=%s warning=%s", ticker, result.warning)
            return []

        events: list[NewsEvent] = []
        for article in result.articles:
            published_at = _parse_published_at(article.published_at)
            if published_at is None:
                continue
            classification = self._classifier.classify(article.title, None)
            candidate = NewsEvent(
                ticker=ticker,
                company=company_name,
                published_at=published_at,
                source=article.source,
                headline=article.title,
                url=article.url,
                event_type=classification.event_type,
                sentiment=classification.sentiment,
                sentiment_score=classification.sentiment_score,
                importance_score=classification.importance_score,
                market_timing=classify_market_timing(published_at),
            )
            novelty = compute_novelty_score(candidate, recent_events + events)
            events.append(candidate.model_copy(update={"novelty_score": novelty}))
        return events
