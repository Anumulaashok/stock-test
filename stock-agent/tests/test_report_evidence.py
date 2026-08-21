from decimal import Decimal

from app.models.analyst import AnalystEvidence
from app.models.financial_results import FinancialAnalysisResult, FinancialMetricResult
from app.models.financial_results import MetricStatus as FMS
from app.models.research import ResearchItem, ResearchResult, ResearchSource
from app.models.scoring import CategoryScore, RiskIndicator, ScoreStatus, ScoringResult, Severity
from app.models.valuation import ValuationRange, ValuationResult
from app.reporting.evidence import filter_evidence, valid_report_evidence_names


def d(value) -> Decimal:
    return Decimal(str(value))


def _financial_analysis():
    return FinancialAnalysisResult(
        company="Acme", periods_analyzed=["FY2024"],
        metrics=[FinancialMetricResult(name="roe", value=d(20), unit="%", status=FMS.CALCULATED)],
    )


def _valuation():
    return ValuationRange(company="Acme", results=[ValuationResult(method="dcf", value_per_share=d(100), status=FMS.CALCULATED)])


def _scoring():
    return ScoringResult(
        company_name="Acme", overall_score=d(70), overall_status=ScoreStatus.CALCULATED,
        category_scores=[CategoryScore(category="profitability", score=d(70), weight=d("1.0"), status=ScoreStatus.CALCULATED)],
        risk_indicators=[RiskIndicator(name="high_debt_to_equity", severity=Severity.HIGH, status=ScoreStatus.CALCULATED, reason="x")],
    )


def _research():
    item = ResearchItem(id="research_001", title="News", source=ResearchSource(title="News", url="https://a.com/1"))
    return ResearchResult(status="success", items=[item], retrieved_at="2026-01-01T00:00:00+00:00")


def test_valid_financial_evidence_includes_metrics_and_categories():
    names = valid_report_evidence_names(_financial_analysis(), _valuation(), _scoring(), _research())
    assert "roe" in names["financial"]
    assert "profitability" in names["financial"]


def test_valid_valuation_evidence():
    names = valid_report_evidence_names(_financial_analysis(), _valuation(), _scoring(), _research())
    assert "dcf" in names["valuation"]


def test_valid_risk_evidence():
    names = valid_report_evidence_names(_financial_analysis(), _valuation(), _scoring(), _research())
    assert "high_debt_to_equity" in names["risk"]


def test_valid_research_evidence():
    names = valid_report_evidence_names(_financial_analysis(), _valuation(), _scoring(), _research())
    assert "research_001" in names["research"]


def test_research_evidence_empty_when_research_unavailable():
    names = valid_report_evidence_names(_financial_analysis(), _valuation(), _scoring(), None)
    assert names["research"] == set()


def test_invalid_financial_reference_filtered_with_warning():
    names = valid_report_evidence_names(_financial_analysis(), _valuation(), _scoring(), _research())
    evidence = AnalystEvidence(financial=["roe", "made_up_metric"])
    filtered, warnings = filter_evidence(evidence, names)
    assert filtered.financial == ["roe"]
    assert any("made_up_metric" in w for w in warnings)


def test_invalid_valuation_reference_filtered_with_warning():
    names = valid_report_evidence_names(_financial_analysis(), _valuation(), _scoring(), _research())
    evidence = AnalystEvidence(valuation=["dcf", "made_up_method"])
    filtered, warnings = filter_evidence(evidence, names)
    assert filtered.valuation == ["dcf"]
    assert any("made_up_method" in w for w in warnings)


def test_invalid_risk_reference_filtered_with_warning():
    names = valid_report_evidence_names(_financial_analysis(), _valuation(), _scoring(), _research())
    evidence = AnalystEvidence(risk=["high_debt_to_equity", "fake_risk"])
    filtered, warnings = filter_evidence(evidence, names)
    assert filtered.risk == ["high_debt_to_equity"]
    assert any("fake_risk" in w for w in warnings)


def test_invalid_research_reference_filtered_with_warning():
    names = valid_report_evidence_names(_financial_analysis(), _valuation(), _scoring(), _research())
    evidence = AnalystEvidence(research=["research_001", "research_999"])
    filtered, warnings = filter_evidence(evidence, names)
    assert filtered.research == ["research_001"]
    assert any("research_999" in w for w in warnings)


def test_invalid_references_never_survive_into_filtered_evidence():
    names = valid_report_evidence_names(_financial_analysis(), _valuation(), _scoring(), _research())
    evidence = AnalystEvidence(financial=["bad1"], valuation=["bad2"], risk=["bad3"], research=["bad4"])
    filtered, warnings = filter_evidence(evidence, names)
    assert filtered.financial == []
    assert filtered.valuation == []
    assert filtered.risk == []
    assert filtered.research == []
    assert len(warnings) == 4
