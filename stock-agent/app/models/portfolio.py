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


class WatchlistCreateRequest(BaseModel):
    ticker: str = Field(min_length=1)
