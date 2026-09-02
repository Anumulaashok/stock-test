"""Maps IndianAPI's `/stock` and `/historical_data` schemas into canonical
`MarketQuote`/`HistoricalPricePoint` models. Pure functions only — no HTTP.

Verified live against `stock.indianapi.in`:
- `/stock` includes `currentPrice: {"BSE": "<price>", "NSE": "<price>"}`
  (either side may be `null` or `"0.00"` when the company isn't listed
  on that exchange) plus `stockDetailsReusableData` (`price`, `close`,
  `percentChange`, `date`, `time`).
- `/historical_data?filter=price` returns
  `{"datasets": [{"metric": "Price", "values": [["YYYY-MM-DD", "<price>"], ...]}]}`
  — only a single daily price per point (no separate open/high/low), so
  `HistoricalPricePoint.open/high/low/close` are all set to that value.

This provider is India-only (NSE/BSE) — currency is always "INR", the
same certainty level already applied in `app.data.mappers.indianapi`.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from app.models.market import HistoricalPricePoint, MarketQuote, MarketStatus, PriceFreshness

_STALE_AFTER_SECONDS = 24 * 60 * 60


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return decimal_value


def _extract_current_price(raw: dict) -> Decimal | None:
    """Prefers NSE over BSE (arbitrary but consistent); falls back to the
    other exchange when one is missing or reported as a zero placeholder."""
    current_price = raw.get("currentPrice")
    if not isinstance(current_price, dict):
        return None
    for exchange in ("NSE", "BSE"):
        value = _to_decimal(current_price.get(exchange))
        if value is not None and value != 0:
            return value
    return None


def _extract_market_timestamp(raw: dict) -> str | None:
    details = raw.get("stockDetailsReusableData")
    if not isinstance(details, dict):
        return None
    date_str, time_str = details.get("date"), details.get("time")
    if not isinstance(date_str, str) or not isinstance(time_str, str):
        return None
    try:
        parsed = datetime.strptime(f"{date_str} {time_str}", "%d %b %Y %H:%M:%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc).isoformat()


def _determine_freshness(current_price: Decimal | None, market_timestamp: str | None, now: datetime) -> PriceFreshness:
    if current_price is None:
        return PriceFreshness.UNAVAILABLE
    if market_timestamp is None:
        return PriceFreshness.DELAYED
    try:
        market_dt = datetime.fromisoformat(market_timestamp)
    except ValueError:
        return PriceFreshness.DELAYED
    age_seconds = (now - market_dt).total_seconds()
    if age_seconds < 0:
        return PriceFreshness.DELAYED
    if age_seconds > _STALE_AFTER_SECONDS:
        return PriceFreshness.STALE
    return PriceFreshness.DELAYED


def map_quote(raw: dict, ticker: str, now: datetime | None = None) -> MarketQuote:
    now = now or datetime.now(timezone.utc)
    current_price = _extract_current_price(raw)
    market_timestamp = _extract_market_timestamp(raw)

    details = raw.get("stockDetailsReusableData")
    previous_close = _to_decimal(details.get("close")) if isinstance(details, dict) else None
    change_percent = _to_decimal(raw.get("percentChange"))
    change = (
        current_price - previous_close
        if current_price is not None and previous_close is not None
        else None
    )

    return MarketQuote(
        ticker=ticker,
        current_price=current_price,
        previous_close=previous_close,
        change=change,
        change_percent=change_percent,
        currency="INR",
        market_status=MarketStatus.UNKNOWN,
        market_timestamp=market_timestamp,
        data_timestamp=now.isoformat(),
        freshness=_determine_freshness(current_price, market_timestamp, now),
        source="indianapi",
    )


def map_historical_prices(raw: dict) -> list[HistoricalPricePoint]:
    datasets = raw.get("datasets")
    if not isinstance(datasets, list):
        return []

    price_dataset = next(
        (d for d in datasets if isinstance(d, dict) and d.get("metric") == "Price"), None
    )
    if price_dataset is None:
        return []

    values = price_dataset.get("values")
    if not isinstance(values, list):
        return []

    points: list[HistoricalPricePoint] = []
    for entry in values:
        if not isinstance(entry, list) or len(entry) != 2:
            continue
        date, price = entry
        if not isinstance(date, str) or not date.strip():
            continue
        close = _to_decimal(price)
        if close is None:
            continue
        points.append(
            HistoricalPricePoint(timestamp=date, open=close, high=close, low=close, close=close)
        )
    return points
