from decimal import Decimal

from app.models.financial_results import MetricStatus
from app.models.forecasting import MovingAverageCrossover, MovingAverageResult, TechnicalForecast
from app.reporting.technical_signal import compute_technical_signal


def d(value) -> Decimal:
    return Decimal(str(value))


def _technical(
    signal: str | None,
    current_price: Decimal | None,
    sma_50: Decimal | None,
    sma_200: Decimal | None,
    crossover_status: MetricStatus = MetricStatus.CALCULATED,
) -> TechnicalForecast:
    return TechnicalForecast(
        ticker="ACME",
        based_on_points=210,
        current_price=current_price,
        moving_averages=[
            MovingAverageResult(window=50, value=sma_50, status=MetricStatus.CALCULATED if sma_50 is not None else MetricStatus.UNAVAILABLE),
            MovingAverageResult(window=200, value=sma_200, status=MetricStatus.CALCULATED if sma_200 is not None else MetricStatus.UNAVAILABLE),
        ],
        crossover=MovingAverageCrossover(short_window=50, long_window=200, signal=signal, status=crossover_status),
    )


def test_no_technical_forecast_is_unavailable():
    signal = compute_technical_signal(None)
    assert signal.label == "unavailable"
    assert signal.color == "gray"


def test_crossover_unavailable_is_unavailable():
    technical = _technical(None, d(100), None, None, crossover_status=MetricStatus.UNAVAILABLE)
    signal = compute_technical_signal(technical)
    assert signal.label == "unavailable"
    assert signal.color == "gray"


def test_golden_cross_with_price_above_both_averages_is_bullish():
    technical = _technical("golden_cross", d(120), d(110), d(100))
    signal = compute_technical_signal(technical)
    assert signal.label == "bullish"
    assert signal.color == "green"
    assert "golden cross" in signal.reason.lower()


def test_golden_cross_with_price_below_an_average_is_mixed():
    technical = _technical("golden_cross", d(95), d(110), d(100))
    signal = compute_technical_signal(technical)
    assert signal.label == "mixed"
    assert signal.color == "yellow"


def test_death_cross_with_price_below_both_averages_is_bearish():
    technical = _technical("death_cross", d(80), d(90), d(100))
    signal = compute_technical_signal(technical)
    assert signal.label == "bearish"
    assert signal.color == "red"
    assert "death cross" in signal.reason.lower()


def test_death_cross_with_price_above_an_average_is_mixed():
    technical = _technical("death_cross", d(105), d(90), d(100))
    signal = compute_technical_signal(technical)
    assert signal.label == "mixed"
    assert signal.color == "yellow"


def test_neutral_crossover_is_neutral():
    technical = _technical("neutral", d(100), d(100), d(100))
    signal = compute_technical_signal(technical)
    assert signal.label == "neutral"
    assert signal.color == "yellow"


def test_never_says_buy_sell_or_hold():
    for scenario in [
        _technical("golden_cross", d(120), d(110), d(100)),
        _technical("death_cross", d(80), d(90), d(100)),
        _technical("neutral", d(100), d(100), d(100)),
        None,
    ]:
        signal = compute_technical_signal(scenario)
        for banned in ("buy", "sell", "hold"):
            assert banned not in signal.label.lower()
            assert banned not in signal.reason.lower()
