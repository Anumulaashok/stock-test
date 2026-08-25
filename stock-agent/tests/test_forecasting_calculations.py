from decimal import Decimal

from app.forecasting.calculations import calculate_cagr, fit_linear_trend, project_metric
from app.models.financial_results import MetricStatus


def d(value) -> Decimal:
    return Decimal(str(value))


# --- calculate_cagr --------------------------------------------------------------------


def test_calculate_cagr_hand_calculated():
    # 100 -> 121 over 2 periods => 10% CAGR
    cagr, status, reason = calculate_cagr(d(100), d(121), 2)
    assert status is MetricStatus.CALCULATED
    assert reason is None
    assert cagr == d(10)


def test_calculate_cagr_single_period_is_yoy_growth():
    cagr, status, _ = calculate_cagr(d(100), d(150), 1)
    assert status is MetricStatus.CALCULATED
    assert cagr == d(50)


def test_calculate_cagr_missing_begin_is_unavailable():
    cagr, status, reason = calculate_cagr(None, d(100), 2)
    assert cagr is None
    assert status is MetricStatus.UNAVAILABLE
    assert reason is not None


def test_calculate_cagr_missing_end_is_unavailable():
    cagr, status, _ = calculate_cagr(d(100), None, 2)
    assert cagr is None
    assert status is MetricStatus.UNAVAILABLE


def test_calculate_cagr_zero_periods_is_unavailable():
    cagr, status, _ = calculate_cagr(d(100), d(150), 0)
    assert cagr is None
    assert status is MetricStatus.UNAVAILABLE


def test_calculate_cagr_zero_begin_is_unavailable():
    cagr, status, _ = calculate_cagr(d(0), d(100), 2)
    assert cagr is None
    assert status is MetricStatus.UNAVAILABLE


def test_calculate_cagr_sign_flip_is_invalid():
    cagr, status, reason = calculate_cagr(d(100), d(-50), 2)
    assert cagr is None
    assert status is MetricStatus.INVALID
    assert "sign" in reason


def test_calculate_cagr_negative_to_less_negative_is_invalid():
    cagr, status, _ = calculate_cagr(d(-100), d(-50), 2)
    assert cagr is None
    assert status is MetricStatus.INVALID


def test_calculate_cagr_decline_is_negative_percent():
    cagr, status, _ = calculate_cagr(d(100), d(81), 2)
    assert status is MetricStatus.CALCULATED
    assert cagr == d(-10)


# --- project_metric ---------------------------------------------------------------------


def test_project_metric_compounds_forward():
    metric = project_metric(
        name="revenue", unit="USD", base_period="FY2025", base_value=d(100),
        cagr_percent=d(10), cagr_status=MetricStatus.CALCULATED, cagr_reason=None,
        periods_used=["FY2024", "FY2025"], projection_years=3,
    )
    assert metric.status is MetricStatus.CALCULATED
    assert [p.value for p in metric.projections] == [d(110), d(121), d("133.1")]
    assert all(p.status is MetricStatus.CALCULATED for p in metric.projections)


def test_project_metric_propagates_unavailable_status_per_year():
    metric = project_metric(
        name="revenue", unit="USD", base_period=None, base_value=None,
        cagr_percent=None, cagr_status=MetricStatus.UNAVAILABLE,
        cagr_reason="insufficient historical periods to calculate growth",
        periods_used=[], projection_years=2,
    )
    assert metric.status is MetricStatus.UNAVAILABLE
    assert len(metric.projections) == 2
    assert all(p.value is None and p.status is MetricStatus.UNAVAILABLE for p in metric.projections)


# --- fit_linear_trend --------------------------------------------------------------------


def test_fit_linear_trend_perfect_line():
    values = [d(10), d(20), d(30), d(40), d(50)]
    slope, intercept, r_squared, status, reason = fit_linear_trend(values)
    assert status is MetricStatus.CALCULATED
    assert reason is None
    assert slope == d(10)
    assert intercept == d(10)
    assert r_squared == d(1)


def test_fit_linear_trend_requires_minimum_points():
    slope, intercept, r_squared, status, reason = fit_linear_trend([d(1), d(2)])
    assert slope is None
    assert status is MetricStatus.UNAVAILABLE
    assert "5" in reason


def test_fit_linear_trend_flat_series_has_zero_slope():
    values = [d(100)] * 6
    slope, _, r_squared, status, _ = fit_linear_trend(values)
    assert status is MetricStatus.CALCULATED
    assert slope == d(0)
    assert r_squared == d(1)
