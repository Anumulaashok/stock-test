from decimal import Decimal

from app.models.financial_results import FinancialMetricResult
from app.models.financial_results import MetricStatus as FinancialMetricStatus
from app.models.scoring import ScoreStatus
from app.scoring.cash_flow import calculate_cash_flow_score
from app.scoring.financial_health import calculate_financial_health_score
from app.scoring.growth import calculate_growth_score
from app.scoring.profitability import calculate_profitability_score


def d(value) -> Decimal:
    return Decimal(str(value))


def calc(name, value, unit="%"):
    return FinancialMetricResult(name=name, value=d(value), unit=unit, status=FinancialMetricStatus.CALCULATED)


def unavailable(name, reason="missing"):
    return FinancialMetricResult(name=name, value=None, unit="%", status=FinancialMetricStatus.UNAVAILABLE, reason=reason)


def invalid(name, reason="bad"):
    return FinancialMetricResult(name=name, value=None, unit="%", status=FinancialMetricStatus.INVALID, reason=reason)


# --- Profitability -----------------------------------------------------------------


def test_profitability_all_metrics_available():
    metrics = {
        "gross_margin": calc("gross_margin", 50),
        "operating_margin": calc("operating_margin", 20),
        "net_margin": calc("net_margin", 15),
        "fcf_margin": calc("fcf_margin", 15),
        "roe": calc("roe", 20),
        "roa": calc("roa", 10),
        "roic": calc("roic", 15),
    }
    result = calculate_profitability_score(metrics, d("0.20"))
    assert result.status is ScoreStatus.CALCULATED
    assert result.score is not None
    assert len(result.components) == 7


def test_profitability_some_unavailable_not_treated_as_zero():
    strong_metrics = {
        "gross_margin": calc("gross_margin", 60),
        "operating_margin": calc("operating_margin", 30),
        "net_margin": calc("net_margin", 20),
        "fcf_margin": calc("fcf_margin", 20),
        "roe": calc("roe", 25),
        "roa": calc("roa", 15),
        "roic": calc("roic", 20),
    }
    full_score = calculate_profitability_score(strong_metrics, d("0.20")).score

    partial_metrics = dict(strong_metrics)
    del partial_metrics["roic"]
    partial_score = calculate_profitability_score(partial_metrics, d("0.20")).score

    # All remaining metrics are maxed out (score 100), so removing ROIC
    # (rather than making it 0) should not lower the score.
    assert partial_score == full_score == d(100)


def test_profitability_all_unavailable():
    result = calculate_profitability_score({}, d("0.20"))
    assert result.status is ScoreStatus.UNAVAILABLE
    assert result.score is None


def test_profitability_invalid_metric_excluded_like_unavailable():
    metrics = {"roe": invalid("roe", "equity is negative")}
    result = calculate_profitability_score(metrics, d("0.20"))
    assert result.status is ScoreStatus.UNAVAILABLE  # only metric provided is invalid


# --- Growth ------------------------------------------------------------------------


def test_growth_extreme_outlier_is_capped():
    metrics = {"revenue_growth": calc("revenue_growth", 100000)}
    result = calculate_growth_score(metrics, d("0.15"))
    assert result.score == d(100)  # capped, not proportional to the raw number


def test_growth_missing_previous_period_style_unavailable():
    metrics = {"revenue_growth": unavailable("revenue_growth", "insufficient historical periods")}
    result = calculate_growth_score(metrics, d("0.15"))
    assert result.status is ScoreStatus.UNAVAILABLE


# --- Financial health ---------------------------------------------------------------


def test_financial_health_all_available():
    metrics = {
        "current_ratio": calc("current_ratio", 2, unit="ratio"),
        "cash_ratio": calc("cash_ratio", "0.8", unit="ratio"),
        "debt_to_equity": calc("debt_to_equity", "0.5", unit="ratio"),
        "debt_to_fcf": calc("debt_to_fcf", 2, unit="ratio"),
        "interest_coverage": calc("interest_coverage", 8, unit="ratio"),
    }
    result = calculate_financial_health_score(metrics, d("0.20"))
    assert result.status is ScoreStatus.CALCULATED
    assert d(0) <= result.score <= d(100)


def test_financial_health_extreme_debt_scores_low():
    metrics = {"debt_to_equity": calc("debt_to_equity", 10, unit="ratio")}
    result = calculate_financial_health_score(metrics, d("0.20"))
    # Only component available -> its score becomes the category score.
    assert result.score == d(0)


def test_financial_health_zero_debt_scores_hundred():
    metrics = {"debt_to_equity": calc("debt_to_equity", 0, unit="ratio")}
    result = calculate_financial_health_score(metrics, d("0.20"))
    assert result.score == d(100)


# --- Cash flow -----------------------------------------------------------------------


def test_cash_flow_negative_fcf_scores_low_but_does_not_crash():
    metrics = {
        "free_cash_flow": calc("free_cash_flow", -500, unit="USD"),
        "fcf_margin": calc("fcf_margin", -10),
        "fcf_growth": calc("fcf_growth", -30),
    }
    result = calculate_cash_flow_score(metrics, d("0.15"))
    assert result.status is ScoreStatus.CALCULATED
    assert result.score < d(30)


def test_cash_flow_positive_and_growing_scores_well():
    metrics = {
        "free_cash_flow": calc("free_cash_flow", 1000, unit="USD"),
        "fcf_margin": calc("fcf_margin", 20),
        "fcf_growth": calc("fcf_growth", 40),
    }
    result = calculate_cash_flow_score(metrics, d("0.15"))
    assert result.score == d(100)


def test_cash_flow_all_unavailable_does_not_crash():
    result = calculate_cash_flow_score({}, d("0.15"))
    assert result.status is ScoreStatus.UNAVAILABLE
    assert result.score is None
