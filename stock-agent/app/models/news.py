"""News domain models — headlines only, never a trading signal on their
own. Used by the Market Opportunity sector ranking (as a small, capped
modifier on top of deterministic fundamentals/technicals) and by the
Ask AI assistant's grounding context.
"""

from pydantic import BaseModel


class NewsArticle(BaseModel):
    title: str
    url: str
    source: str | None = None
    published_at: str | None = None


class NewsResult(BaseModel):
    status: str  # "success" | "unavailable"
    provider: str | None = None
    articles: list[NewsArticle] = []
    warning: str | None = None
