"""Research/market-context domain models.

This is EXTERNAL, QUALITATIVE CONTEXT — never a source of financial
metrics, valuation, scores, or risk severity. Every `ResearchItem` keeps
its source attributable (title, publisher, URL, publication date) so a
claim can always be traced back to where it came from; nothing here
represents anonymous, uncited text.

`ResearchErrorCode`/`ResearchError` follow the same structured,
non-throwing pattern already used for `AnalystResult` (Step 5) and
`FinancialDataFetchResult` (Step 7).
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    NEWS = "news"
    COMPANY = "company"
    REGULATORY = "regulatory"
    MARKET = "market"
    OTHER = "other"


class ResearchFreshness(StrEnum):
    RECENT = "recent"
    STALE = "stale"
    UNKNOWN = "unknown"


class ResearchErrorCode(StrEnum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    INVALID_RESPONSE = "invalid_response"
    UNSUPPORTED_QUERY = "unsupported_query"
    INVALID_QUERY = "invalid_query"


class ResearchError(BaseModel):
    code: ResearchErrorCode
    message: str


class ResearchQuery(BaseModel):
    """Constructed deterministically from company name/ticker — never by
    the LLM (see Step 8 report)."""

    company_name: str
    ticker: str | None = None
    topics: list[str] = Field(default_factory=list)
    date_range_days: int | None = Field(
        default=None, description="None = use the research service's configured default."
    )
    max_results: int | None = Field(
        default=None, description="None = use the research service's configured default."
    )


class ResearchSource(BaseModel):
    """Attribution for one research item. `url` is always a validated
    http(s) URL — `file://`, `javascript:`, `data:`, and any other
    non-http(s) scheme are rejected before an item is ever built."""

    title: str
    publisher: str | None = None
    url: str
    published_at: str | None = Field(
        default=None, description="ISO 8601 timestamp; None if the source didn't report one."
    )
    source_type: SourceType = SourceType.NEWS


class ResearchItem(BaseModel):
    """One piece of external context. `id` is a stable, referenceable
    identifier (e.g. 'research_001') the analyst can cite as evidence —
    the response validator checks any cited id actually exists here."""

    id: str
    title: str
    summary: str | None = None
    source: ResearchSource
    published_at: str | None = None
    freshness: ResearchFreshness = ResearchFreshness.UNKNOWN
    relevance: Decimal | None = Field(
        default=None, description="Deterministic 0-1 relevance score; never LLM-assigned."
    )
    topic: str | None = None


class ResearchResult(BaseModel):
    """The outcome of one research retrieval. Always returned — never
    raises past `ResearchService` — so a failed/unavailable research
    provider degrades to `status='error'` with an empty item list rather
    than breaking the caller."""

    status: str  # "success" | "error"
    items: list[ResearchItem] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: ResearchError | None = None
    retrieved_at: str
