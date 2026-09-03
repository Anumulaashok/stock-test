"""Maps yfinance's `fast_info`/`history` schemas into canonical
`MarketQuote`/`HistoricalPricePoint` models. Pure functions only -- no
yfinance calls (see `app.market.providers.yfinance_client`).

Field provenance verified live against RELIANCE.NS (2026-09-03): `fast_info`
gives `lastPrice`, `previousClose`, `marketCap`, `yearHigh`, `yearLow`,
`currency`; `history()` gives real per-day `open`/`high`/`low`/`close`/`volume`
(unlike IndianAPI's historical endpoint, which only reports one daily price).

yfinance is an unofficial, reverse-engineered API with no documented
real-time SLA and no reliable per-quote timestamp -- like FMP's mapper,
this always reports `DELAYED` (never `LIVE`) rather than assert freshness
it can't verify.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from app.models.market import HistoricalPricePoint, MarketQuote, MarketStatus, PriceFreshness


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def map_quote(raw: dict, ticker: str, now: datetime | None = None) -> MarketQuote:
    now = now or datetime.now(timezone.utc)
    current_price = _to_decimal(raw.get("lastPrice"))
    previous_close = _to_decimal(raw.get("previousClose"))
    change = (
        current_price - previous_close
        if current_price is not None and previous_close is not None
        else None
    )
    change_percent = (
        (change / previous_close * 100)
        if change is not None and previous_close not in (None, Decimal(0))
        else None
    )

    return MarketQuote(
        ticker=ticker,
        current_price=current_price,
        previous_close=previous_close,
        change=change,
        change_percent=change_percent,
        currency=raw.get("currency") if isinstance(raw.get("currency"), str) else None,
        market_status=MarketStatus.UNKNOWN,
        market_timestamp=None,
        data_timestamp=now.isoformat(),
        freshness=PriceFreshness.DELAYED if current_price is not None else PriceFreshness.UNAVAILABLE,
        source="yfinance",
        market_cap=_to_decimal(raw.get("marketCap")),
        year_high=_to_decimal(raw.get("yearHigh")),
        year_low=_to_decimal(raw.get("yearLow")),
    )


def map_historical_prices(raw_records: list[dict]) -> list[HistoricalPricePoint]:
    points: list[HistoricalPricePoint] = []
    for raw in raw_records:
        date = raw.get("date")
        if not isinstance(date, str) or not date.strip():
            continue
        points.append(
            HistoricalPricePoint(
                timestamp=date,
                open=_to_decimal(raw.get("open")),
                high=_to_decimal(raw.get("high")),
                low=_to_decimal(raw.get("low")),
                close=_to_decimal(raw.get("close")),
                volume=_to_decimal(raw.get("volume")),
            )
        )
    return points
