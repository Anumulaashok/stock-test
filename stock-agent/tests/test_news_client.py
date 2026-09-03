"""Tests for `NewsClient` -- mocked HTTP against both providers,
verifying the newsdata.io -> newsapi.org fallback and that every
failure mode returns `status="unavailable"` rather than raising."""

import httpx
import pytest
import respx

from app.news.client import NewsClient

NEWSDATA_BASE = "http://test-newsdata:9999/api/1"
NEWSAPI_BASE = "http://test-newsapi:9999/v2"


def _client(newsdata_key: str | None = "nd-key", newsapi_key: str | None = "na-key") -> NewsClient:
    return NewsClient(
        newsdata_api_key=newsdata_key,
        newsdata_base_url=NEWSDATA_BASE,
        newsapi_api_key=newsapi_key,
        newsapi_base_url=NEWSAPI_BASE,
    )


@pytest.mark.asyncio
@respx.mock
async def test_search_returns_articles_from_newsdata_when_configured():
    respx.get(f"{NEWSDATA_BASE}/news").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "results": [
                    {"title": "Healthcare stocks rally", "link": "https://example.com/1", "source_id": "et", "pubDate": "2026-09-01"}
                ],
            },
        )
    )

    result = await _client().search("Healthcare sector India stocks")

    assert result.status == "success"
    assert result.provider == "newsdata"
    assert len(result.articles) == 1
    assert result.articles[0].title == "Healthcare stocks rally"


@pytest.mark.asyncio
@respx.mock
async def test_falls_back_to_newsapi_when_newsdata_fails():
    respx.get(f"{NEWSDATA_BASE}/news").mock(return_value=httpx.Response(500))
    respx.get(f"{NEWSAPI_BASE}/everything").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "ok",
                "articles": [
                    {"title": "IT sector outlook", "url": "https://example.com/2", "source": {"name": "moneycontrol"}, "publishedAt": "2026-09-01T00:00:00Z"}
                ],
            },
        )
    )

    result = await _client().search("IT sector India stocks")

    assert result.status == "success"
    assert result.provider == "newsapi"
    assert result.articles[0].title == "IT sector outlook"


@pytest.mark.asyncio
async def test_unavailable_when_no_provider_configured():
    client = _client(newsdata_key=None, newsapi_key=None)

    result = await client.search("anything")

    assert result.status == "unavailable"
    assert result.articles == []


@pytest.mark.asyncio
@respx.mock
async def test_both_providers_failing_returns_unavailable_not_raise():
    respx.get(f"{NEWSDATA_BASE}/news").mock(return_value=httpx.Response(500))
    respx.get(f"{NEWSAPI_BASE}/everything").mock(return_value=httpx.Response(500))

    result = await _client().search("anything")

    assert result.status == "unavailable"
