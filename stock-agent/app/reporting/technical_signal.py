"""Derives a deterministic, color-coded technical-trend signal from an
already-computed `TechnicalForecast`.

This is explicitly NOT a buy/sell/hold recommendation, and mirrors
`app/reporting/signal.py`'s boundary: it recolors a combination of
signals that already exist (the moving-average crossover, and whether
the current price is trading above or below each moving average) — it
never computes a new number, fits a new trend, or outputs "buy",
"sell", or "hold". A reader still decides what (if anything) to do with
"bullish"/"bearish" — this only names the direction the already-computed
evidence points, the same way `compute_signal` names score strength.
"""

from app.models.forecasting import TechnicalForecast
from app.models.report import ReportTechnicalSignal


def compute_technical_signal(technical: TechnicalForecast | None) -> ReportTechnicalSignal:
    """Never fabricates a signal for missing data — insufficient price
    history gets `label="unavailable"`, never a guessed direction."""
    if technical is None or technical.crossover is None or technical.crossover.status.value != "calculated":
        return ReportTechnicalSignal(
            label="unavailable",
            color="gray",
            reason="Not enough price history was available to compute a moving-average crossover signal.",
        )

    crossover = technical.crossover
    current_price = technical.current_price
    sma_by_window = {ma.window: ma for ma in technical.moving_averages}
    short_sma = sma_by_window.get(crossover.short_window)
    long_sma = sma_by_window.get(crossover.long_window)

    def _above(sma) -> bool | None:
        if current_price is None or sma is None or sma.status.value != "calculated" or sma.value is None:
            return None
        return current_price > sma.value

    above_short = _above(short_sma)
    above_long = _above(long_sma)
    price_confirms_bullish = above_short is True and above_long is True
    price_confirms_bearish = above_short is False and above_long is False

    if crossover.signal == "golden_cross":
        if price_confirms_bullish:
            return ReportTechnicalSignal(
                label="bullish",
                color="green",
                reason=(
                    f"The {crossover.short_window}-day moving average is above the "
                    f"{crossover.long_window}-day (golden cross), and the current price is "
                    "trading above both."
                ),
            )
        return ReportTechnicalSignal(
            label="mixed",
            color="yellow",
            reason=(
                f"A golden cross ({crossover.short_window}-day above {crossover.long_window}-day) "
                "was detected, but the current price is not confirming it by trading above both "
                "moving averages."
            ),
        )

    if crossover.signal == "death_cross":
        if price_confirms_bearish:
            return ReportTechnicalSignal(
                label="bearish",
                color="red",
                reason=(
                    f"The {crossover.short_window}-day moving average is below the "
                    f"{crossover.long_window}-day (death cross), and the current price is "
                    "trading below both."
                ),
            )
        return ReportTechnicalSignal(
            label="mixed",
            color="yellow",
            reason=(
                f"A death cross ({crossover.short_window}-day below {crossover.long_window}-day) "
                "was detected, but the current price is not confirming it by trading below both "
                "moving averages."
            ),
        )

    return ReportTechnicalSignal(
        label="neutral",
        color="yellow",
        reason=(
            f"The {crossover.short_window}-day and {crossover.long_window}-day moving averages "
            "are effectively equal -- no clear crossover trend."
        ),
    )
