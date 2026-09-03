"""What each data source can actually provide.

A provider declares only the capabilities its code genuinely implements.
The distinction this module exists to preserve: a source being
*configured* is not the same as it being *capable* of a category, which
is not the same as it being *active* for that category on a given call.
"""

from enum import StrEnum


class Capability(StrEnum):
    COMPANY_SEARCH = "company_search"
    QUOTE = "quote"
    OHLCV = "ohlcv"
    # Close + moving averages + volume, without true open/high/low. Screener's
    # chart endpoint returns this shape; calling it OHLCV would overstate it.
    DAILY_CLOSE_SERIES = "daily_close_series"
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"
    HISTORICAL_FINANCIALS = "historical_financials"


class Category(StrEnum):
    """A request category, resolved against one provider chain."""

    FINANCIALS = "financials"
    MARKET_QUOTE = "market_quote"
    HISTORICAL_PRICE = "historical_price"
    COMPANY_SEARCH = "company_search"


# Which capabilities a provider must declare to serve a category at all.
CATEGORY_REQUIREMENTS: dict[Category, frozenset[Capability]] = {
    Category.FINANCIALS: frozenset(
        {Capability.INCOME_STATEMENT, Capability.BALANCE_SHEET, Capability.CASH_FLOW}
    ),
    Category.MARKET_QUOTE: frozenset({Capability.QUOTE}),
    Category.HISTORICAL_PRICE: frozenset({Capability.OHLCV, Capability.DAILY_CLOSE_SERIES}),
    Category.COMPANY_SEARCH: frozenset({Capability.COMPANY_SEARCH}),
}


def can_serve(capabilities: frozenset[Capability], category: Category) -> bool:
    """A provider serves a category if it declares *any* capability the
    category accepts — financial statements are useful even when only a
    subset of the three statements is available, and historical price is
    satisfied by either true OHLCV or a close-only series."""
    return bool(capabilities & CATEGORY_REQUIREMENTS[category])
