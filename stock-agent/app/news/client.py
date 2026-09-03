"""HTTP client for headline news, used only as a small, capped modifier
on top of deterministic fundamentals/technicals (never a standalone
signal, never fed to the LLM as fact without attribution).

Two independent providers are supported — newsdata.io (primary, if
configured) and newsapi.org (fallback, if configured). Neither is
required: `NewsClient` is only constructed when at least one API key is
present (see `app/api/dependencies.py`), and every failure mode here
returns `NewsResult(status="unavailable", ...)` rather than raising, so
a news outage never breaks sector ranking or Ask AI.
"""

import logging

import httpx

from app.models.news import NewsArticle, NewsResult

logger = logging.getLogger(__name__)


class NewsClient:
    def __init__(
        self,
        newsdata_api_key: str | None,
        newsdata_base_url: str,
        newsapi_api_key: str | None,
        newsapi_base_url: str,
        connect_timeout_seconds: float = 5.0,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._newsdata_api_key = newsdata_api_key
        self._newsdata_base_url = newsdata_base_url.rstrip("/")
        self._newsapi_api_key = newsapi_api_key
        self._newsapi_base_url = newsapi_base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout=timeout_seconds, connect=connect_timeout_seconds)

    async def search(self, query: str, limit: int = 5) -> NewsResult:
        if self._newsdata_api_key:
            result = await self._search_newsdata(query, limit)
            if result.status == "success":
                return result
            logger.info("newsdata.io unavailable for query=%s (%s); falling back", query, result.warning)

        if self._newsapi_api_key:
            return await self._search_newsapi(query, limit)

        return NewsResult(status="unavailable", warning="No news provider configured")

    async def _search_newsdata(self, query: str, limit: int) -> NewsResult:
        params = {"apikey": self._newsdata_api_key, "q": query, "language": "en"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._newsdata_base_url}/news", params=params)
        except httpx.RequestError as exc:
            return NewsResult(status="unavailable", provider="newsdata", warning=f"request failed: {exc}")

        if response.status_code != 200:
            return NewsResult(
                status="unavailable", provider="newsdata", warning=f"status {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError:
            return NewsResult(status="unavailable", provider="newsdata", warning="malformed JSON response")

        if payload.get("status") != "success":
            return NewsResult(
                status="unavailable", provider="newsdata", warning=str(payload.get("results", "error"))
            )

        articles = [
            NewsArticle(
                title=item.get("title", ""),
                url=item.get("link", ""),
                source=item.get("source_id"),
                published_at=item.get("pubDate"),
            )
            for item in payload.get("results", [])[:limit]
            if item.get("title") and item.get("link")
        ]
        return NewsResult(status="success", provider="newsdata", articles=articles)

    async def _search_newsapi(self, query: str, limit: int) -> NewsResult:
        params = {
            "apiKey": self._newsapi_api_key,
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": limit,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._newsapi_base_url}/everything", params=params)
        except httpx.RequestError as exc:
            return NewsResult(status="unavailable", provider="newsapi", warning=f"request failed: {exc}")

        if response.status_code != 200:
            return NewsResult(
                status="unavailable", provider="newsapi", warning=f"status {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError:
            return NewsResult(status="unavailable", provider="newsapi", warning="malformed JSON response")

        if payload.get("status") != "ok":
            return NewsResult(
                status="unavailable", provider="newsapi", warning=str(payload.get("message", "error"))
            )

        articles = [
            NewsArticle(
                title=item.get("title", ""),
                url=item.get("url", ""),
                source=(item.get("source") or {}).get("name"),
                published_at=item.get("publishedAt"),
            )
            for item in payload.get("articles", [])[:limit]
            if item.get("title") and item.get("url")
        ]
        return NewsResult(status="success", provider="newsapi", articles=articles)
