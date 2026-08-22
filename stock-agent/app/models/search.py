"""Stock search/autocomplete domain model.

Kept separate from `financial_statements.py`/`market.py` — a search
result is a lightweight suggestion (symbol + name), never a source of
financial or price data.
"""

from pydantic import BaseModel


class StockSearchResult(BaseModel):
    """One ticker suggestion, sourced from a local, static equity list
    (see `app/search/service.py`) — never fetched over the network per
    keystroke."""

    symbol: str
    name: str
    exchange: str = "NSE"
    isin: str | None = None
