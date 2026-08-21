"""Maps FMP's market-quote/historical-price schema into canonical
`MarketQuote`/`HistoricalPricePoint` models. Pure functions only — no HTTP.

See `app.market.providers.fmp_client` for the field-name provenance
caveat (documented from FMP's own docs + third-party corroboration, not
independently live-verified the way Steps 7/8 verified their providers).
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from app.models.market import HistoricalPricePoint, MarketQuote, MarketStatus, PriceFreshness

# A quote older than this (relative to when we fetched it) is treated as
# stale rather than merely delayed — centralizes the one threshold this
# mapper applies rather than burying it in a conditional.
_STALE_AFTER_SECONDS = 24 * 60 * 60


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_iso_timestamp(value: object) -> str | None:
    """FMP reports quote timestamps as Unix seconds."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _determine_freshness(
    current_price: Decimal | None, market_timestamp: str | None, now: datetime
) -> PriceFreshness:
    if current_price is None:
        return PriceFreshness.UNAVAILABLE
    if market_timestamp is None:
        # We have a price but can't verify its age — never claim LIVE
        # without evidence; DELAYED is the honest middle ground.
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
    # FMP's free/standard quote endpoint is not guaranteed true real-time
    # for every plan — DELAYED is the honest default rather than LIVE.
    return PriceFreshness.DELAYED


def map_quote(raw: dict, ticker: str, now: datetime | None = None) -> MarketQuote:
    now = now or datetime.now(timezone.utc)
    current_price = _to_decimal(raw.get("price"))
    market_timestamp = _to_iso_timestamp(raw.get("timestamp"))

    return MarketQuote(
        ticker=ticker,
        current_price=current_price,
        previous_close=_to_decimal(raw.get("previousClose")),
        change=_to_decimal(raw.get("change")),
        change_percent=_to_decimal(raw.get("changePercentage")),
        currency=raw.get("currency") if isinstance(raw.get("currency"), str) else None,
        market_status=MarketStatus.UNKNOWN,
        market_timestamp=market_timestamp,
        data_timestamp=now.isoformat(),
        freshness=_determine_freshness(current_price, market_timestamp, now),
        source="fmp",
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
                adjusted_close=_to_decimal(raw.get("adjClose")),
                volume=_to_decimal(raw.get("volume")),
            )
        )
    return points
