from decimal import Decimal

from app.models.financial_results import MetricStatus
from app.models.valuation import ValuationInput
from app.valuation.service import ValuationService


def d(value) -> Decimal:
    return Decimal(str(value))


def _result(range_, method):
    matches = [r for r in range_.results if r.method == method]
    assert len(matches) == 1
    return matches[0]


def test_service_runs_all_methods_independently_without_averaging():
    valuation_input = ValuationInput(
        company_name="Acme Corp",
        current_share_price=d(50),
        shares_outstanding=d(10),
        free_cash_flow=d(100),
        eps=d("2.50"),
        ebitda=d(100),
        total_debt=d(50),
        cash=d(20),
        fcf_growth_rate=d("0.10"),
        discount_rate=d("0.25"),
        terminal_growth_rate=d("0.05"),
        projection_years=1,
        target_pe=d(20),
        target_ev_ebitda=d(8),
        target_pfcf=d(15),
    )

    result = ValuationService().analyze(valuation_input)

    assert result.company == "Acme Corp"
    assert {r.method for r in result.results} == {"dcf", "pe", "ev_ebitda", "pfcf"}

    dcf_result = _result(result, "dcf")
    pe_result = _result(result, "pe")
    assert dcf_result.value_per_share == d("54.2")
    assert pe_result.value_per_share == d(50)
    # Methods are not blended into a single number anywhere in the result.
    assert dcf_result.value_per_share != pe_result.value_per_share


def test_service_attaches_upside_downside_when_current_price_available():
    valuation_input = ValuationInput(
        company_name="Acme Corp",
        current_share_price=d(40),
        eps=d("2.50"),
        target_pe=d(20),  # -> value_per_share = 50
    )

    result = ValuationService().analyze(valuation_input)
    pe_result = _result(result, "pe")

    assert pe_result.upside_downside_status is MetricStatus.CALCULATED
    assert pe_result.upside_downside_percent == d(25)  # (50-40)/40*100


def test_service_reports_upside_downside_unavailable_without_current_price():
    valuation_input = ValuationInput(
        company_name="Acme Corp",
        eps=d("2.50"),
        target_pe=d(20),
    )

    result = ValuationService().analyze(valuation_input)
    pe_result = _result(result, "pe")

    # value_per_share is still calculated; only upside/downside is affected,
    # and it is reported as unavailable (with a reason) rather than silently
    # left absent.
    assert pe_result.status is MetricStatus.CALCULATED
    assert pe_result.upside_downside_status is MetricStatus.UNAVAILABLE
    assert pe_result.upside_downside_percent is None
    assert "current share price" in pe_result.upside_downside_reason


def test_service_one_available_method_others_unavailable():
    valuation_input = ValuationInput(
        company_name="Acme Corp",
        eps=d("2.50"),
        target_pe=d(20),
    )

    result = ValuationService().analyze(valuation_input)

    assert _result(result, "pe").status is MetricStatus.CALCULATED
    assert _result(result, "dcf").status is MetricStatus.UNAVAILABLE
    assert _result(result, "ev_ebitda").status is MetricStatus.UNAVAILABLE
    assert _result(result, "pfcf").status is MetricStatus.UNAVAILABLE


def test_service_no_inputs_all_methods_unavailable():
    valuation_input = ValuationInput(company_name="Empty Co")
    result = ValuationService().analyze(valuation_input)

    assert all(r.status is MetricStatus.UNAVAILABLE for r in result.results)
    assert all(r.value_per_share is None for r in result.results)
