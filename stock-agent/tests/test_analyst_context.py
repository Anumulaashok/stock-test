from decimal import Decimal

from app.analyst.context import build_analyst_context, valid_evidence_names
from app.models.financial_results import FinancialAnalysisResult, FinancialMetricResult
from app.models.financial_results import MetricStatus as FMS
from app.models.financial_statements import CompanyFinancials
from app.models.research import ResearchError, ResearchErrorCode, ResearchItem, ResearchResult, ResearchSource
from app.models.scoring import CategoryScore, RiskIndicator, ScoreStatus, ScoringResult, Severity
from app.models.valuation import ValuationRange, ValuationResult


def d(value) -> Decimal:
    return Decimal(str(value))


def _financial_analysis(**overrides):
    defaults = dict(
        company="Acme Corp",
        periods_analyzed=["FY2024", "FY2025"],
        metrics=[
            FinancialMetricResult(name="roe", value=d(20), unit="%", status=FMS.CALCULATED),
            FinancialMetricResult(
                name="revenue_growth", value=None, unit="%", status=FMS.UNAVAILABLE,
                reason="previous-period revenue is missing",
            ),
        ],
        warnings=["Only one fiscal period of data is available; growth metrics are unavailable."],
    )
    defaults.update(overrides)
    return FinancialAnalysisResult(**defaults)


def _scoring(**overrides):
    defaults = dict(
        company_name="Acme Corp",
        overall_score=d(78),
        overall_status=ScoreStatus.CALCULATED,
        band=None,
        category_scores=[
            CategoryScore(category="profitability", score=d(87), weight=d("0.20"), status=ScoreStatus.CALCULATED),
            CategoryScore(
                category="valuation", score=None, weight=d("0.20"), status=ScoreStatus.UNAVAILABLE,
                reason="No valuation data was provided.",
            ),
        ],
        risk_indicators=[
            RiskIndicator(
                name="high_debt_to_equity", severity=Severity.HIGH, status=ScoreStatus.CALCULATED,
                value=d(3), threshold=d(2), reason="debt/equity is at or above the high risk threshold",
            )
        ],
        warnings=["Valuation category was unavailable and excluded from the overall score."],
    )
    defaults.update(overrides)
    return ScoringResult(**defaults)


def test_context_includes_company_name_and_ticker():
    company_financials = CompanyFinancials(company_name="Acme Corp", ticker="ACME")
    context = build_analyst_context(_financial_analysis(), None, _scoring(), company_financials)
    assert context.company.name == "Acme Corp"
    assert context.company.ticker == "ACME"


def test_context_ticker_none_without_company_financials():
    context = build_analyst_context(_financial_analysis(), None, _scoring(), None)
    assert context.company.ticker is None


def test_context_preserves_calculated_and_unavailable_metrics():
    context = build_analyst_context(_financial_analysis(), None, _scoring())
    by_name = {m.name: m for m in context.financial_metrics}
    assert by_name["roe"].status == "calculated"
    assert by_name["roe"].value == d(20)
    assert by_name["revenue_growth"].status == "unavailable"
    assert by_name["revenue_growth"].value is None
    assert by_name["revenue_growth"].reason == "previous-period revenue is missing"


def test_context_preserves_financial_warnings():
    context = build_analyst_context(_financial_analysis(), None, _scoring())
    assert context.financial_warnings == [
        "Only one fiscal period of data is available; growth metrics are unavailable."
    ]


def test_context_valuation_none_yields_empty_methods_and_no_price():
    context = build_analyst_context(_financial_analysis(), None, _scoring())
    assert context.valuation_methods == []
    assert context.current_share_price is None


def test_context_valuation_present_preserves_methods_and_price():
    valuation = ValuationRange(
        company="Acme Corp",
        current_share_price=d(150),
        results=[
            ValuationResult(
                method="dcf", value_per_share=d(180), status=FMS.CALCULATED,
                upside_downside_percent=d(20), upside_downside_status=FMS.CALCULATED,
            ),
            ValuationResult(
                method="pe", value_per_share=None, status=FMS.INVALID,
                reason="target P/E multiple must be positive",
            ),
        ],
        warnings=[],
    )
    context = build_analyst_context(_financial_analysis(), valuation, _scoring())
    assert context.current_share_price == d(150)
    by_method = {m.method: m for m in context.valuation_methods}
    assert by_method["dcf"].value_per_share == d(180)
    assert by_method["dcf"].upside_downside_percent == d(20)
    assert by_method["pe"].status == "invalid"
    assert by_method["pe"].value_per_share is None


def test_context_preserves_scoring_categories_and_risk_indicators():
    context = build_analyst_context(_financial_analysis(), None, _scoring())
    assert context.overall_score == d(78)
    assert context.overall_status == "calculated"
    profitability = next(c for c in context.category_scores if c.category == "profitability")
    assert profitability.score == d(87)
    valuation_cat = next(c for c in context.category_scores if c.category == "valuation")
    assert valuation_cat.status == "unavailable"
    assert valuation_cat.reason == "No valuation data was provided."

    risk = context.risk_indicators[0]
    assert risk.name == "high_debt_to_equity"
    assert risk.severity == "high"


def test_context_preserves_scoring_warnings():
    context = build_analyst_context(_financial_analysis(), None, _scoring())
    assert "Valuation category was unavailable and excluded from the overall score." in context.scoring_warnings


def test_valid_evidence_names_covers_all_categories():
    context = build_analyst_context(_financial_analysis(), None, _scoring())
    names = valid_evidence_names(context)
    assert "roe" in names["financial"]
    assert "revenue_growth" in names["financial"]
    assert "profitability" in names["financial"]  # category-score names live under "financial" too
    assert "valuation" in names["financial"]
    assert "high_debt_to_equity" in names["risk"]
    assert "nonexistent_metric" not in names["financial"]
    assert names["research"] == set()  # no research supplied in this fixture


def _successful_research():
    item = ResearchItem(
        id="research_001", title="Acme Corp expands", summary="Summary text",
        source=ResearchSource(title="Acme Corp expands", publisher="Example News", url="https://example.com/a",
                               published_at="2026-01-01T00:00:00+00:00"),
        published_at="2026-01-01T00:00:00+00:00",
    )
    return ResearchResult(status="success", items=[item], sources=[item.source], retrieved_at="2026-01-10T00:00:00+00:00")


def test_context_includes_research_when_available():
    context = build_analyst_context(_financial_analysis(), None, _scoring(), research=_successful_research())
    assert context.research_available is True
    assert len(context.research_items) == 1
    assert context.research_items[0].id == "research_001"
    assert context.research_items[0].publisher == "Example News"


def test_context_omits_research_when_unavailable():
    error_research = ResearchResult(
        status="error", error=ResearchError(code=ResearchErrorCode.PROVIDER_UNAVAILABLE, message="down"),
        retrieved_at="2026-01-10T00:00:00+00:00",
    )
    context = build_analyst_context(_financial_analysis(), None, _scoring(), research=error_research)
    assert context.research_available is False
    assert context.research_items == []
    assert "down" in context.research_warnings


def test_context_no_research_supplied_at_all():
    context = build_analyst_context(_financial_analysis(), None, _scoring(), research=None)
    assert context.research_available is False
    assert context.research_items == []


def test_valid_evidence_names_includes_research_item_ids():
    context = build_analyst_context(_financial_analysis(), None, _scoring(), research=_successful_research())
    names = valid_evidence_names(context)
    assert "research_001" in names["research"]
