from decimal import Decimal

from app.models.financial_results import FinancialMetricResult
from app.models.financial_results import MetricStatus as FinancialMetricStatus
from app.models.scoring import ScoreStatus
from app.scoring.aggregation import aggregate_category, aggregate_overall, score_metric
from app.scoring.thresholds import LinearBand
from app.scoring.normalization import normalize_linear_higher_is_better


def d(value) -> Decimal:
    return Decimal(str(value))


BAND = LinearBand(floor=d(0), target=d(20))


def _calc_metric(name, value):
    return FinancialMetricResult(
        name=name, value=d(value), unit="%", status=FinancialMetricStatus.CALCULATED, source_periods=["FY2024"]
    )


def _unavailable_metric(name, reason="missing"):
    return FinancialMetricResult(name=name, value=None, unit="%", status=FinancialMetricStatus.UNAVAILABLE, reason=reason)


def _invalid_metric(name, reason="bad"):
    return FinancialMetricResult(name=name, value=None, unit="%", status=FinancialMetricStatus.INVALID, reason=reason)


def test_score_metric_calculated():
    metrics = {"roe": _calc_metric("roe", 10)}
    component = score_metric(metrics, "roe", d("0.5"), lambda v: normalize_linear_higher_is_better(v, BAND))
    assert component.status is ScoreStatus.CALCULATED
    assert component.score == d(50)
    assert component.value == d(10)


def test_score_metric_missing_entirely():
    component = score_metric({}, "roe", d("0.5"), lambda v: normalize_linear_higher_is_better(v, BAND))
    assert component.status is ScoreStatus.UNAVAILABLE
    assert component.score is None


def test_score_metric_propagates_unavailable():
    metrics = {"roe": _unavailable_metric("roe", "equity is zero")}
    component = score_metric(metrics, "roe", d("0.5"), lambda v: normalize_linear_higher_is_better(v, BAND))
    assert component.status is ScoreStatus.UNAVAILABLE
    assert component.reason == "equity is zero"


def test_score_metric_propagates_invalid():
    metrics = {"roe": _invalid_metric("roe", "equity is negative")}
    component = score_metric(metrics, "roe", d("0.5"), lambda v: normalize_linear_higher_is_better(v, BAND))
    assert component.status is ScoreStatus.INVALID


def test_aggregate_category_all_available():
    from app.models.scoring import ScoreComponent

    components = [
        ScoreComponent(name="a", score=d(80), weight=d("0.5"), status=ScoreStatus.CALCULATED),
        ScoreComponent(name="b", score=d(40), weight=d("0.5"), status=ScoreStatus.CALCULATED),
    ]
    result = aggregate_category("profitability", components, d("0.20"))
    assert result.status is ScoreStatus.CALCULATED
    assert result.score == d(60)
    assert result.reason is None


def test_aggregate_category_renormalizes_over_available_only():
    from app.models.scoring import ScoreComponent

    components = [
        ScoreComponent(name="a", score=d(80), weight=d("0.5"), status=ScoreStatus.CALCULATED),
        ScoreComponent(name="b", score=None, weight=d("0.5"), status=ScoreStatus.UNAVAILABLE, reason="x"),
    ]
    result = aggregate_category("profitability", components, d("0.20"))
    assert result.status is ScoreStatus.CALCULATED
    # Missing component is excluded, not treated as zero -> score stays 80.
    assert result.score == d(80)
    assert "1 of 2" in result.reason


def test_aggregate_category_all_unavailable():
    from app.models.scoring import ScoreComponent

    components = [
        ScoreComponent(name="a", score=None, weight=d("0.5"), status=ScoreStatus.UNAVAILABLE, reason="x"),
        ScoreComponent(name="b", score=None, weight=d("0.5"), status=ScoreStatus.INVALID, reason="y"),
    ]
    result = aggregate_category("profitability", components, d("0.20"))
    assert result.status is ScoreStatus.UNAVAILABLE
    assert result.score is None


def test_aggregate_overall_renormalizes_over_available_categories():
    from app.models.scoring import CategoryScore

    categories = [
        CategoryScore(category="profitability", score=d(80), weight=d("0.5"), status=ScoreStatus.CALCULATED),
        CategoryScore(category="growth", score=None, weight=d("0.5"), status=ScoreStatus.UNAVAILABLE, reason="no data"),
    ]
    overall, status, warnings = aggregate_overall(categories)
    assert status is ScoreStatus.CALCULATED
    assert overall == d(80)
    assert any("Growth" in w for w in warnings)


def test_aggregate_overall_all_unavailable():
    from app.models.scoring import CategoryScore

    categories = [
        CategoryScore(category="profitability", score=None, weight=d("0.5"), status=ScoreStatus.UNAVAILABLE, reason="x"),
    ]
    overall, status, warnings = aggregate_overall(categories)
    assert status is ScoreStatus.UNAVAILABLE
    assert overall is None
