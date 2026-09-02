"""Presentation formatting — pure functions, no calculation.

These only produce a display string alongside a value; they never
replace or mutate the canonical `Decimal` the string was derived from.
Rounding happens only here, at the presentation boundary — every
upstream model keeps full precision.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.reporting.constants import CURRENCY_QUANT, PERCENT_QUANT, RATIO_QUANT, SCORE_QUANT


def format_percent(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value.quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)}%"


def format_currency(value: Decimal | None, currency: str | None = None) -> str | None:
    if value is None:
        return None
    rounded = value.quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP)
    prefix = "$" if not currency or currency == "USD" else f"{currency} "
    return f"{prefix}{rounded:,}"


def format_score(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)}"


def format_ratio(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value.quantize(RATIO_QUANT, rounding=ROUND_HALF_UP)}"


def format_metric_value(value: Decimal | None, unit: str | None, currency: str | None = None) -> str | None:
    """Formats a `FinancialMetricResult`/`ScoreComponent`-style value
    according to its declared unit, without touching the underlying value.

    `unit == "USD"` is this codebase's generic tag for "this is a
    currency-denominated value" (see `app/financial/calculations.py`),
    not a literal assertion that the value is in US dollars — the actual
    display currency is `currency` (the company's real reporting
    currency, e.g. "INR"), which wins over the tag when supplied.
    """
    if value is None:
        return None
    if unit == "%":
        return format_percent(value)
    if unit == "USD":
        return format_currency(value, currency)
    if unit == "ratio":
        return format_ratio(value)
    return str(value)
