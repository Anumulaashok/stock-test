"""FinnhubProvider: implements `ResearchProvider` for Finnhub company news.

Combines `FinnhubClient` (HTTP) and the Finnhub mapper so Finnhub's field
names never leak past this module — downstream code only sees
`ResearchItem`.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from app.models.research import ResearchErrorCode, ResearchItem, ResearchQuery
from app.research.base import ResearchProvider
from app.research.exceptions import ResearchProviderError
from app.research.mappers.finnhub import map_articles
from app.research.providers.finnhub_client import FinnhubClient

logger = logging.getLogger(__name__)


class FinnhubProvider(ResearchProvider):
    def __init__(
        self,
        client: FinnhubClient,
        default_date_range_days: int = 30,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._default_date_range_days = default_date_range_days
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def search(self, query: ResearchQuery) -> tuple[list[ResearchItem], list[str]]:
        if not query.ticker:
            raise ResearchProviderError(
                ResearchErrorCode.UNSUPPORTED_QUERY,
                "Finnhub's company-news endpoint requires a ticker symbol",
            )

        now = self._clock()
        days = query.date_range_days or self._default_date_range_days
        from_date = (now - timedelta(days=days)).date().isoformat()
        to_date = now.date().isoformat()

        raw_records = await self._client.get_company_news(query.ticker, from_date, to_date)
        return map_articles(raw_records)
