from decimal import Decimal

from app.models.financial_results import FinancialAnalysisResult, FinancialMetricResult
from app.models.financial_results import MetricStatus as FMS
from app.models.financial_statements import BalanceSheet, CompanyFinancials, IncomeStatement
from app.pipeline.adapters import build_valuation_input
from app.pipeline.models import AnalysisRequest


def d(value) -> Decimal:
    return Decimal(str(value))


def _company_financials():
    return CompanyFinancials(
        company_name="Acme Corp",
        income_statements=[
            IncomeStatement(period="FY2024", revenue=d(1000), net_income=d(100), eps=d("2.00"), shares_outstanding=d(50)),
        ],
        balance_sheets=[
            BalanceSheet(period="FY2024", total_debt=d(200), cash_and_equivalents=d(80)),
        ],
    )


def _financial_analysis(fcf_value=d(150), fcf_status=FMS.CALCULATED, fcf_growth_value=None, fcf_growth_status=FMS.UNAVAILABLE):
    metrics = [
        FinancialMetricResult(name="free_cash_flow", value=fcf_value, unit="USD", status=fcf_status, reason=None if fcf_status == FMS.CALCULATED else "operating cash flow is missing"),
    ]
    if fcf_growth_status is not FMS.UNAVAILABLE or fcf_growth_value is not None:
        metrics.append(
            FinancialMetricResult(name="fcf_growth", value=fcf_growth_value, unit="%", status=fcf_growth_status, reason=None)
        )
    return FinancialAnalysisResult(company="Acme Corp", periods_analyzed=["FY2024"], metrics=metrics)


def _request(**overrides):
    defaults = dict(company_name="Acme Corp", ticker="ACME", company_financials=_company_financials())
    defaults.update(overrides)
    return AnalysisRequest(**defaults)


def test_derives_values_from_latest_period_when_not_explicit():
    valuation_input, _warnings = build_valuation_input(_request(), _financial_analysis())
    assert valuation_input.shares_outstanding == d(50)
    assert valuation_input.eps == d("2.00")
    assert valuation_input.total_debt == d(200)
    assert valuation_input.cash == d(80)
    assert valuation_input.revenue == d(1000)
    assert valuation_input.net_income == d(100)
    assert valuation_input.free_cash_flow == d(150)


def test_explicit_request_values_override_derived_ones():
    request = _request(shares_outstanding=d(999), eps=d("9.99"), total_debt=d(1), cash=d(2))
    valuation_input, _warnings = build_valuation_input(request, _financial_analysis())
    assert valuation_input.shares_outstanding == d(999)
    assert valuation_input.eps == d("9.99")
    assert valuation_input.total_debt == d(1)
    assert valuation_input.cash == d(2)


def test_assumptions_passed_through_only_when_explicitly_supplied():
    request = _request(
        discount_rate=d("0.09"), terminal_growth_rate=d("0.025"), projection_years=5,
        fcf_growth_rate=d("0.08"), target_pe=d(20), target_ev_ebitda=d(10), target_pfcf=d(15),
        current_share_price=d(150), ebitda=d(300),
    )
    valuation_input, warnings = build_valuation_input(request, _financial_analysis())
    assert valuation_input.discount_rate == d("0.09")
    assert valuation_input.terminal_growth_rate == d("0.025")
    assert valuation_input.projection_years == 5
    assert valuation_input.fcf_growth_rate == d("0.08")
    assert valuation_input.target_pe == d(20)
    assert valuation_input.target_ev_ebitda == d(10)
    assert valuation_input.target_pfcf == d(15)
    assert valuation_input.current_share_price == d(150)
    assert valuation_input.ebitda == d(300)
    assert warnings == []  # every assumption was explicit -- nothing to warn about


def test_multiple_target_assumptions_never_invented():
    valuation_input, _warnings = build_valuation_input(_request(), _financial_analysis())
    assert valuation_input.target_pe is None
    assert valuation_input.target_ev_ebitda is None
    assert valuation_input.target_pfcf is None
    assert valuation_input.ebitda is None
    assert valuation_input.current_share_price is None


def test_no_periods_analyzed_leaves_derived_fields_none():
    empty_analysis = FinancialAnalysisResult(company="Acme Corp", periods_analyzed=[], metrics=[])
    valuation_input, _warnings = build_valuation_input(_request(), empty_analysis)
    assert valuation_input.shares_outstanding is None
    assert valuation_input.total_debt is None
    assert valuation_input.cash is None
    assert valuation_input.eps is None
    assert valuation_input.revenue is None


def test_unavailable_fcf_metric_leaves_free_cash_flow_none_not_zero():
    valuation_input, _warnings = build_valuation_input(
        _request(), _financial_analysis(fcf_value=None, fcf_status=FMS.UNAVAILABLE)
    )
    assert valuation_input.free_cash_flow is None


def test_missing_statement_for_latest_period_leaves_fields_none():
    financials = CompanyFinancials(company_name="Acme Corp", income_statements=[], balance_sheets=[])
    analysis = FinancialAnalysisResult(company="Acme Corp", periods_analyzed=["FY2024"], metrics=[])
    valuation_input, _warnings = build_valuation_input(_request(company_financials=financials), analysis)
    assert valuation_input.shares_outstanding is None
    assert valuation_input.total_debt is None


# --- auto-derived DCF assumptions -----------------------------------------------------------


def test_no_auto_derivation_without_free_cash_flow():
    # DCF is unavailable regardless of assumptions when there's no FCF base
    # -- auto-deriving assumptions for it would be pointless, so nothing
    # is defaulted and there's nothing to warn about.
    valuation_input, warnings = build_valuation_input(
        _request(), _financial_analysis(fcf_value=None, fcf_status=FMS.UNAVAILABLE)
    )
    assert valuation_input.discount_rate is None
    assert valuation_input.terminal_growth_rate is None
    assert valuation_input.projection_years is None
    assert valuation_input.fcf_growth_rate is None
    assert warnings == []


def test_discount_rate_and_terminal_growth_and_projection_years_get_defaults():
    valuation_input, warnings = build_valuation_input(_request(), _financial_analysis())
    assert valuation_input.discount_rate == d("0.10")
    assert valuation_input.terminal_growth_rate == d("0.025")
    assert valuation_input.projection_years == 5
    assert any("Discount rate" in w for w in warnings)
    assert any("Terminal growth rate" in w for w in warnings)


def test_fcf_growth_rate_auto_derived_from_historical_fcf_growth_metric():
    analysis = _financial_analysis(fcf_growth_value=d(15), fcf_growth_status=FMS.CALCULATED)
    valuation_input, warnings = build_valuation_input(_request(), analysis)
    assert valuation_input.fcf_growth_rate == d("0.15")
    assert any("auto-derived from historical FCF growth" in w for w in warnings)


def test_fcf_growth_rate_auto_derivation_is_capped():
    # 127.87% historical growth (a low-base artifact) must not be
    # compounded for 5 years -- clamped to the documented cap.
    analysis = _financial_analysis(fcf_growth_value=d("127.87"), fcf_growth_status=FMS.CALCULATED)
    valuation_input, warnings = build_valuation_input(_request(), analysis)
    assert valuation_input.fcf_growth_rate == d("0.20")
    assert any("capped to 20.00%" in w for w in warnings)


def test_fcf_growth_rate_auto_derivation_capped_on_the_downside_too():
    analysis = _financial_analysis(fcf_growth_value=d("-90"), fcf_growth_status=FMS.CALCULATED)
    valuation_input, _warnings = build_valuation_input(_request(), analysis)
    assert valuation_input.fcf_growth_rate == d("-0.20")


def test_fcf_growth_rate_not_auto_derived_when_metric_is_invalid():
    analysis = _financial_analysis(fcf_growth_value=None, fcf_growth_status=FMS.INVALID)
    valuation_input, warnings = build_valuation_input(_request(), analysis)
    assert valuation_input.fcf_growth_rate is None
    assert not any("fcf growth" in w.lower() and "auto-derived" in w for w in warnings)


def test_explicit_fcf_growth_rate_is_never_clamped_or_overridden():
    request = _request(fcf_growth_rate=d("0.50"))
    analysis = _financial_analysis(fcf_growth_value=d("15"), fcf_growth_status=FMS.CALCULATED)
    valuation_input, warnings = build_valuation_input(request, analysis)
    assert valuation_input.fcf_growth_rate == d("0.50")
    assert not any("auto-derived" in w for w in warnings)
