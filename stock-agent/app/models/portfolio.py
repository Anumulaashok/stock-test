"""Portfolio/watchlist API models.

`current_price`/`market_value`/`unrealized_gain*` are never stored —
they are computed at request time from `quantity`/`average_cost` plus a
live `MarketQuote` (see `app/market/`). When a price is unavailable,
these fields are `None`, never `0` — see `PortfolioService`.
"""

from decimal import Decimal

from pydantic import BaseModel, Field


class HoldingCreateRequest(BaseModel):
    ticker: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    average_cost: Decimal = Field(gt=0)


class HoldingUpdateRequest(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0)
    average_cost: Decimal | None = Field(default=None, gt=0)


class Holding(BaseModel):
    id: str
    ticker: str
    quantity: Decimal
    average_cost: Decimal
    added_at: str
    updated_at: str


class HoldingWithMarketData(Holding):
    current_price: Decimal | None
    price_status: str  # a `PriceFreshness` value, or "unavailable"
    market_value: Decimal | None
    unrealized_gain: Decimal | None
    unrealized_gain_percent: Decimal | None


class PortfolioSummary(BaseModel):
    portfolio_id: str
    invested_capital: Decimal
    portfolio_value: Decimal | None
    unrealized_gain: Decimal | None
    unrealized_gain_percent: Decimal | None
    holdings: list[HoldingWithMarketData] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WatchlistItem(BaseModel):
    ticker: str
    created_at: str


class WatchlistItemEnriched(WatchlistItem):
    """`WatchlistItem` plus a live quote and the latest research score,
    for the Watchlist page's "should I look at this" table. Both halves
    are independently optional -- a ticker can be watchlisted without
    ever having been researched, and a quote can be unavailable while a
    score is not. Never a fabricated 0; missing data is `None`."""

    current_price: Decimal | None = None
    price_status: str = "unavailable"  # a `PriceFreshness` value, or "unavailable"
    change_percent: Decimal | None = None
    overall_score: Decimal | None = None
    band: str | None = None
    last_researched_at: str | None = None


class WatchlistCreateRequest(BaseModel):
    ticker: str = Field(min_length=1)
