from decimal import Decimal

from app.models.financial_results import FinancialAnalysisResult, FinancialMetricResult
from app.models.financial_results import MetricStatus as FinancialMetricStatus
from app.models.scoring import ScoreBand, ScoreStatus
from app.models.valuation import ValuationRange, ValuationResult
from app.scoring.service import ScoringService


def d(value) -> Decimal:
    return Decimal(str(value))


def calc(name, value, unit="%"):
    return FinancialMetricResult(name=name, value=d(value), unit=unit, status=FinancialMetricStatus.CALCULATED)


def unavailable(name, reason="missing"):
    return FinancialMetricResult(name=name, value=None, unit="%", status=FinancialMetricStatus.UNAVAILABLE, reason=reason)


def _strong_financials() -> FinancialAnalysisResult:
    return FinancialAnalysisResult(
        company="Acme Corp",
        periods_analyzed=["FY2024"],
        metrics=[
            calc("gross_margin", 55),
            calc("operating_margin", 25),
            calc("net_margin", 18),
            calc("fcf_margin", 18),
            calc("roe", 22),
            calc("roa", 12),
            calc("roic", 18),
            calc("revenue_growth", 20),
            calc("net_income_growth", 25),
            calc("eps_growth", 25),
            calc("fcf_growth", 20),
            calc("current_ratio", 2, unit="ratio"),
            calc("cash_ratio", "0.9", unit="ratio"),
            calc("debt_to_equity", "0.4", unit="ratio"),
            calc("debt_to_fcf", 2, unit="ratio"),
            calc("interest_coverage", 12, unit="ratio"),
            calc("free_cash_flow", 500, unit="USD"),
        ],
    )


def _strong_valuation() -> ValuationRange:
    return ValuationRange(
        company="Acme Corp",
        current_share_price=d(100),
        results=[
            ValuationResult(
                method="dcf", value_per_share=d(140), status=FinancialMetricStatus.CALCULATED,
                upside_downside_percent=d(40), upside_downside_status=FinancialMetricStatus.CALCULATED,
            ),
            ValuationResult(
                method="pe", value_per_share=d(120), status=FinancialMetricStatus.CALCULATED,
                upside_downside_percent=d(20), upside_downside_status=FinancialMetricStatus.CALCULATED,
            ),
            ValuationResult(
                method="ev_ebitda", value_per_share=d(130), status=FinancialMetricStatus.CALCULATED,
                upside_downside_percent=d(30), upside_downside_status=FinancialMetricStatus.CALCULATED,
            ),
            ValuationResult(
                method="pfcf", value_per_share=d(115), status=FinancialMetricStatus.CALCULATED,
                upside_downside_percent=d(15), upside_downside_status=FinancialMetricStatus.CALCULATED,
            ),
        ],
    )


def test_full_pipeline_strong_company_scores_well():
    result = ScoringService().analyze(_strong_financials(), _strong_valuation())

    assert result.company_name == "Acme Corp"
    assert result.overall_status is ScoreStatus.CALCULATED
    assert result.overall_score is not None
    assert result.overall_score >= d(70)
    assert result.band in (ScoreBand.EXCELLENT, ScoreBand.STRONG, ScoreBand.GOOD)
    assert len(result.category_scores) == 6
    assert len(result.risk_indicators) == 10


def test_pipeline_never_crashes_with_no_financial_metrics():
    empty_financials = FinancialAnalysisResult(company="Empty Co", periods_analyzed=[], metrics=[])
    result = ScoringService().analyze(empty_financials, None)

    # Every metric-driven category is unavailable...
    assert all(
        c.status is ScoreStatus.UNAVAILABLE
        for c in result.category_scores
        if c.category != "risk"
    )
    # ...but the risk engine's "missing_critical_data" check still runs and
    # produces a real (poor) signal, so risk — and therefore the overall
    # score — is not itself unavailable. This demonstrates the engine
    # degrades gracefully rather than crashing or going fully blank.
    risk_category = next(c for c in result.category_scores if c.category == "risk")
    assert risk_category.status is ScoreStatus.CALCULATED
    assert result.overall_status is ScoreStatus.CALCULATED
    assert result.overall_score is not None
    assert result.overall_score < d(50)


def test_pipeline_with_only_some_categories_available():
    financials = FinancialAnalysisResult(
        company="Partial Co",
        periods_analyzed=["FY2024"],
        metrics=[calc("roe", 20), calc("current_ratio", 2, unit="ratio")],
    )
    result = ScoringService().analyze(financials, None)

    assert result.overall_status is ScoreStatus.CALCULATED
    assert result.overall_score is not None
    profitability = next(c for c in result.category_scores if c.category == "profitability")
    growth = next(c for c in result.category_scores if c.category == "growth")
    assert profitability.status is ScoreStatus.CALCULATED
    assert growth.status is ScoreStatus.UNAVAILABLE
    assert any("Growth" in w for w in result.warnings)


def test_pipeline_negative_fcf_and_net_income_lowers_but_does_not_crash():
    financials = FinancialAnalysisResult(
        company="Struggling Co",
        periods_analyzed=["FY2024"],
        metrics=[
            calc("net_margin", -15),
            calc("fcf_margin", -20),
            calc("free_cash_flow", -1000, unit="USD"),
            calc("revenue_growth", -25),
        ],
    )
    result = ScoringService().analyze(financials, None)
    assert result.overall_status is ScoreStatus.CALCULATED
    assert result.overall_score < d(50)

    negative_fcf = next(i for i in result.risk_indicators if i.name == "negative_fcf")
    assert negative_fcf.severity is not None


def test_pipeline_no_valuation_data_valuation_category_unavailable():
    result = ScoringService().analyze(_strong_financials(), None)
    valuation_category = next(c for c in result.category_scores if c.category == "valuation")
    assert valuation_category.status is ScoreStatus.UNAVAILABLE
    assert result.overall_status is ScoreStatus.CALCULATED  # other categories still contribute


def test_pipeline_only_multiples_available_no_dcf():
    valuation = ValuationRange(
        company="Acme Corp",
        current_share_price=d(100),
        results=[
            ValuationResult(
                method="pe", value_per_share=d(120), status=FinancialMetricStatus.CALCULATED,
                upside_downside_percent=d(20), upside_downside_status=FinancialMetricStatus.CALCULATED,
            ),
        ],
    )
    result = ScoringService().analyze(_strong_financials(), valuation)
    valuation_category = next(c for c in result.category_scores if c.category == "valuation")
    assert valuation_category.status is ScoreStatus.CALCULATED
    # Risk engine falls back to a non-DCF method when DCF is absent.
    excessive_valuation = next(i for i in result.risk_indicators if i.name == "excessive_valuation")
    assert excessive_valuation.status is ScoreStatus.CALCULATED


def test_pipeline_invalid_valuation_result_does_not_crash():
    valuation = ValuationRange(
        company="Acme Corp",
        results=[
            ValuationResult(
                method="dcf", value_per_share=None, status=FinancialMetricStatus.INVALID,
                reason="terminal growth rate must be less than the discount rate",
            ),
        ],
    )
    result = ScoringService().analyze(_strong_financials(), valuation)
    valuation_category = next(c for c in result.category_scores if c.category == "valuation")
    assert valuation_category.status is ScoreStatus.UNAVAILABLE
    assert valuation_category.components[0].status is ScoreStatus.INVALID


def test_pipeline_current_price_zero_does_not_crash():
    valuation = ValuationRange(
        company="Acme Corp",
        current_share_price=d(0),
        results=[
            ValuationResult(
                method="dcf", value_per_share=d(140), status=FinancialMetricStatus.CALCULATED,
                upside_downside_percent=None, upside_downside_status=FinancialMetricStatus.UNAVAILABLE,
                upside_downside_reason="current share price is zero",
            ),
        ],
    )
    result = ScoringService().analyze(_strong_financials(), valuation)
    assert result.overall_status is ScoreStatus.CALCULATED  # doesn't crash; valuation just unavailable
