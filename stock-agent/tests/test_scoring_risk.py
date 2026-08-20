from decimal import Decimal

from app.models.financial_results import FinancialMetricResult
from app.models.financial_results import MetricStatus as FinancialMetricStatus
from app.models.scoring import ScoreStatus, Severity
from app.models.valuation import ValuationRange, ValuationResult
from app.scoring.risk import calculate_risk_score, detect_risk_indicators


def d(value) -> Decimal:
    return Decimal(str(value))


def calc(name, value, unit="ratio"):
    return FinancialMetricResult(name=name, value=d(value), unit=unit, status=FinancialMetricStatus.CALCULATED)


def _by_name(indicators):
    return {i.name: i for i in indicators}


def test_negative_fcf_triggers_high_severity():
    metrics = {"free_cash_flow": calc("free_cash_flow", -100, unit="USD")}
    indicators = _by_name(detect_risk_indicators(metrics, None))
    assert indicators["negative_fcf"].severity is Severity.HIGH


def test_positive_fcf_not_triggered():
    metrics = {"free_cash_flow": calc("free_cash_flow", 100, unit="USD")}
    indicators = _by_name(detect_risk_indicators(metrics, None))
    assert indicators["negative_fcf"].severity is None
    assert indicators["negative_fcf"].status is ScoreStatus.CALCULATED


def test_missing_fcf_metric_is_unavailable_not_crash():
    indicators = _by_name(detect_risk_indicators({}, None))
    assert indicators["negative_fcf"].status is ScoreStatus.UNAVAILABLE


def test_negative_net_income_via_net_margin():
    metrics = {"net_margin": calc("net_margin", -5)}
    indicators = _by_name(detect_risk_indicators(metrics, None))
    assert indicators["negative_net_income"].severity is Severity.HIGH


def test_high_debt_to_equity_tiers():
    for value, expected in [(1, None), (2, Severity.MEDIUM), (3, Severity.HIGH), (5, Severity.CRITICAL)]:
        metrics = {"debt_to_equity": calc("debt_to_equity", value)}
        indicators = _by_name(detect_risk_indicators(metrics, None))
        assert indicators["high_debt_to_equity"].severity is expected, value


def test_weak_interest_coverage_tiers():
    for value, expected in [(10, None), (4, Severity.MEDIUM), (2, Severity.HIGH), (1, Severity.CRITICAL)]:
        metrics = {"interest_coverage": calc("interest_coverage", value)}
        indicators = _by_name(detect_risk_indicators(metrics, None))
        assert indicators["weak_interest_coverage"].severity is expected, value


def test_weak_liquidity_tiers():
    for value, expected in [(2, None), (1, Severity.MEDIUM), ("0.8", Severity.HIGH), ("0.5", Severity.CRITICAL)]:
        metrics = {"current_ratio": calc("current_ratio", value)}
        indicators = _by_name(detect_risk_indicators(metrics, None))
        assert indicators["weak_liquidity"].severity is expected, value


def test_declining_revenue_tiers():
    for value, expected in [(5, None), (0, None), (-5, Severity.LOW), (-15, Severity.MEDIUM), (-25, Severity.HIGH)]:
        metrics = {"revenue_growth": calc("revenue_growth", value, unit="%")}
        indicators = _by_name(detect_risk_indicators(metrics, None))
        assert indicators["declining_revenue"].severity is expected, value


def test_declining_net_income():
    metrics = {"net_income_growth": calc("net_income_growth", -30, unit="%")}
    indicators = _by_name(detect_risk_indicators(metrics, None))
    assert indicators["declining_net_income"].severity is Severity.HIGH


def test_weak_cash_flow_trend():
    metrics = {"fcf_growth": calc("fcf_growth", -30, unit="%")}
    indicators = _by_name(detect_risk_indicators(metrics, None))
    assert indicators["weak_cash_flow_trend"].severity is Severity.HIGH


def test_excessive_valuation_prefers_dcf():
    valuation = ValuationRange(
        company="Acme",
        results=[
            ValuationResult(
                method="dcf", value_per_share=d(50), status=FinancialMetricStatus.CALCULATED,
                upside_downside_percent=d(-50), upside_downside_status=FinancialMetricStatus.CALCULATED,
            ),
            ValuationResult(
                method="pe", value_per_share=d(90), status=FinancialMetricStatus.CALCULATED,
                upside_downside_percent=d(-5), upside_downside_status=FinancialMetricStatus.CALCULATED,
            ),
        ],
    )
    indicators = _by_name(detect_risk_indicators({}, valuation))
    assert indicators["excessive_valuation"].severity is Severity.HIGH
    assert indicators["excessive_valuation"].value == d(-50)


def test_excessive_valuation_no_data_unavailable():
    indicators = _by_name(detect_risk_indicators({}, None))
    assert indicators["excessive_valuation"].status is ScoreStatus.UNAVAILABLE


def test_missing_critical_data_severity_scales_with_count():
    indicators = _by_name(detect_risk_indicators({}, None))
    # all 4 critical metrics missing -> HIGH (threshold 3+)
    assert indicators["missing_critical_data"].severity is Severity.HIGH

    metrics = {
        "free_cash_flow": calc("free_cash_flow", 100, unit="USD"),
        "net_margin": calc("net_margin", 10),
        "debt_to_equity": calc("debt_to_equity", 1),
        "current_ratio": calc("current_ratio", 2),
    }
    indicators_full = _by_name(detect_risk_indicators(metrics, None))
    assert indicators_full["missing_critical_data"].severity is None


def test_risk_engine_never_crashes_on_empty_input():
    indicators = detect_risk_indicators({}, None)
    assert len(indicators) == 10


def test_calculate_risk_score_no_risks_is_hundred():
    metrics = {
        "free_cash_flow": calc("free_cash_flow", 100, unit="USD"),
        "net_margin": calc("net_margin", 10),
        "debt_to_equity": calc("debt_to_equity", 0),
        "interest_coverage": calc("interest_coverage", 20),
        "current_ratio": calc("current_ratio", 2),
        "revenue_growth": calc("revenue_growth", 10),
        "net_income_growth": calc("net_income_growth", 10),
        "fcf_growth": calc("fcf_growth", 10),
    }
    indicators = detect_risk_indicators(metrics, None)
    category = calculate_risk_score(indicators, d("0.10"))
    assert category.status is ScoreStatus.CALCULATED
    # excessive_valuation is unavailable (no valuation data), rest are clean.
    assert category.score == d(100)


def test_calculate_risk_score_with_critical_triggers_lowers_score():
    metrics = {"debt_to_equity": calc("debt_to_equity", 6)}  # CRITICAL
    indicators = detect_risk_indicators(metrics, None)
    category = calculate_risk_score(indicators, d("0.10"))
    assert category.status is ScoreStatus.CALCULATED
    assert category.score < d(100)
