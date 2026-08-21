"""Market-data domain models — a separate domain from financial
statements (`app/models/financial_statements.py`). A `MarketDataProvider`
supplies current/historical *prices*; it must never be confused with a
`FinancialDataProvider`, which supplies *financial statements*.

Nothing here is ever fabricated: an unavailable price is `None` with
`freshness=UNAVAILABLE`, never `0` or a guessed value. `data_timestamp`
(when *we* retrieved it) is always known; `market_timestamp` (when the
provider says the price is as-of) is preserved separately and may be
`None` if the provider didn't report one.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class MarketStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class PriceFreshness(StrEnum):
    LIVE = "live"
    DELAYED = "delayed"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class MarketDataErrorCode(StrEnum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    TICKER_NOT_FOUND = "ticker_not_found"
    INVALID_RESPONSE = "invalid_response"
    SCHEMA_MISMATCH = "schema_mismatch"


class MarketDataError(BaseModel):
    code: MarketDataErrorCode
    message: str


class MarketQuote(BaseModel):
    ticker: str
    current_price: Decimal | None
    previous_close: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    currency: str | None
    market_status: MarketStatus = MarketStatus.UNKNOWN
    market_timestamp: str | None = None
    data_timestamp: str
    freshness: PriceFreshness
    source: str


class HistoricalPricePoint(BaseModel):
    timestamp: str
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    adjusted_close: Decimal | None = None
    volume: Decimal | None = None


class MarketSnapshot(BaseModel):
    ticker: str
    quote: MarketQuote | None
    recent_prices: list[HistoricalPricePoint] = Field(default_factory=list)
    fetched_at: str
    warnings: list[str] = Field(default_factory=list)


class MarketSnapshotResult(BaseModel):
    """Outcome of one snapshot fetch — mirrors `ResearchResult`'s
    non-throwing status pattern."""

    status: str  # "success" | "error"
    snapshot: MarketSnapshot | None = None
    error: MarketDataError | None = None
