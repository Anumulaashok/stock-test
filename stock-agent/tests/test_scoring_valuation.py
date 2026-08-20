from decimal import Decimal

from app.models.financial_results import MetricStatus
from app.models.scoring import ScoreStatus
from app.models.valuation import ValuationRange, ValuationResult
from app.scoring.valuation import calculate_valuation_score


def d(value) -> Decimal:
    return Decimal(str(value))


def _result(method, value_per_share, status=MetricStatus.CALCULATED, upside=None, upside_status=None, reason=None):
    return ValuationResult(
        method=method,
        value_per_share=value_per_share,
        status=status,
        reason=reason,
        upside_downside_percent=upside,
        upside_downside_status=upside_status,
    )


def test_valuation_all_methods_with_upside():
    valuation = ValuationRange(
        company="Acme",
        current_share_price=d(100),
        results=[
            _result("dcf", d(150), upside=d(50), upside_status=MetricStatus.CALCULATED),
            _result("pe", d(120), upside=d(20), upside_status=MetricStatus.CALCULATED),
            _result("ev_ebitda", d(110), upside=d(10), upside_status=MetricStatus.CALCULATED),
            _result("pfcf", d(90), upside=d(-10), upside_status=MetricStatus.CALCULATED),
        ],
    )
    result = calculate_valuation_score(valuation, d("0.20"))
    assert result.status is ScoreStatus.CALCULATED
    assert len(result.components) == 4


def test_valuation_only_dcf_available():
    valuation = ValuationRange(
        company="Acme",
        current_share_price=d(100),
        results=[_result("dcf", d(150), upside=d(50), upside_status=MetricStatus.CALCULATED)],
    )
    result = calculate_valuation_score(valuation, d("0.20"))
    assert result.status is ScoreStatus.CALCULATED
    assert result.score == d(100)  # 50% upside saturates the band


def test_valuation_no_current_price_component_unavailable():
    valuation = ValuationRange(
        company="Acme",
        current_share_price=None,
        results=[
            _result(
                "pe", d(120), upside=None, upside_status=MetricStatus.UNAVAILABLE,
            )
        ],
    )
    result = calculate_valuation_score(valuation, d("0.20"))
    assert result.status is ScoreStatus.UNAVAILABLE  # only method present has no upside


def test_valuation_invalid_method_propagates_invalid():
    valuation = ValuationRange(
        company="Acme",
        results=[_result("dcf", None, status=MetricStatus.INVALID, reason="terminal growth >= discount rate")],
    )
    result = calculate_valuation_score(valuation, d("0.20"))
    component = result.components[0]
    assert component.status is ScoreStatus.INVALID


def test_valuation_no_data_at_all():
    result = calculate_valuation_score(None, d("0.20"))
    assert result.status is ScoreStatus.UNAVAILABLE


def test_valuation_current_price_zero_unavailable_upside():
    valuation = ValuationRange(
        company="Acme",
        current_share_price=d(0),
        results=[
            _result(
                "pe", d(120), upside=None, upside_status=MetricStatus.UNAVAILABLE,
                reason=None,
            )
        ],
    )
    result = calculate_valuation_score(valuation, d("0.20"))
    assert result.status is ScoreStatus.UNAVAILABLE
