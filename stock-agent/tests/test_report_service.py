from datetime import datetime, timezone
from decimal import Decimal

from app.models.analyst import (
    AnalystError,
    AnalystErrorCode,
    AnalystEvidence,
    AnalystResponse,
    AnalystResult,
    AnalystSection,
)
from app.models.financial_results import FinancialAnalysisResult, FinancialMetricResult
from app.models.financial_results import MetricStatus as FMS
from app.models.report import ReportStatus
from app.models.research import ResearchError, ResearchErrorCode, ResearchItem, ResearchResult, ResearchSource
from app.models.scoring import CategoryScore, RiskIndicator, ScoreComponent, ScoreStatus, ScoringResult, Severity
from app.models.valuation import ValuationRange, ValuationResult
from app.pipeline.models import CombinedAnalysisResult, ExecutionMetadata, PipelineCompanyInfo, PipelineStatus
from app.reporting.service import ReportService


def d(value) -> Decimal:
    return Decimal(str(value))


def _clock():
    return datetime(2026, 3, 1, tzinfo=timezone.utc)


def _financial_analysis():
    return FinancialAnalysisResult(
        company="Acme Corp",
        periods_analyzed=["FY2023", "FY2024"],
        metrics=[
            FinancialMetricResult(name="roe", value=d(24), unit="%", status=FMS.CALCULATED, source_periods=["FY2024"]),
            FinancialMetricResult(name="net_margin", value=d(18), unit="%", status=FMS.CALCULATED, source_periods=["FY2024"]),
            FinancialMetricResult(name="revenue_growth", value=d(15), unit="%", status=FMS.CALCULATED, source_periods=["FY2023", "FY2024"]),
            FinancialMetricResult(name="current_ratio", value=d("1.8"), unit="ratio", status=FMS.CALCULATED, source_periods=["FY2024"]),
            FinancialMetricResult(name="free_cash_flow", value=d(250), unit="USD", status=FMS.CALCULATED, source_periods=["FY2024"]),
            FinancialMetricResult(
                name="fcf_growth", value=None, unit="%", status=FMS.UNAVAILABLE,
                reason="insufficient historical periods to calculate growth",
            ),
        ],
        warnings=["Only two fiscal periods of data are available."],
    )


def _valuation():
    return ValuationRange(
        company="Acme Corp", current_share_price=d(100),
        results=[
            ValuationResult(
                method="dcf", value_per_share=d(140), status=FMS.CALCULATED,
                upside_downside_percent=d(40), upside_downside_status=FMS.CALCULATED,
                assumptions={"discount_rate": d("0.09"), "terminal_growth_rate": d("0.025"), "projection_years": 5},
            ),
            ValuationResult(
                method="pe", value_per_share=None, status=FMS.UNAVAILABLE, reason="EPS is missing",
            ),
        ],
        warnings=["target EV/EBITDA multiple is missing"],
    )


def _scoring():
    return ScoringResult(
        company_name="Acme Corp", overall_score=d(78), overall_status=ScoreStatus.CALCULATED, band="good",
        category_scores=[
            CategoryScore(
                category="profitability", score=d(85), weight=d("0.20"), status=ScoreStatus.CALCULATED,
                components=[
                    ScoreComponent(
                        name="roe", score=d(90), weight=d("0.5"), status=ScoreStatus.CALCULATED, reason="ROE is strong",
                    )
                ],
            ),
            CategoryScore(category="valuation", score=None, weight=d("0.20"), status=ScoreStatus.UNAVAILABLE, reason="No valuation data was provided."),
        ],
        risk_indicators=[
            RiskIndicator(name="high_debt_to_equity", severity=Severity.HIGH, status=ScoreStatus.CALCULATED, value=d(3), threshold=d(2), reason="debt/equity is elevated"),
            RiskIndicator(name="negative_fcf", severity=None, status=ScoreStatus.CALCULATED, value=d(250), threshold=d(0), reason="free cash flow is not negative"),
        ],
        warnings=["Valuation category was unavailable and excluded from the overall score."],
    )


def _research():
    item = ResearchItem(
        id="research_001", title="Acme Corp expands into new market", summary="Expansion summary.",
        source=ResearchSource(title="Acme Corp expands into new market", publisher="Example News", url="https://example.com/a", published_at="2026-02-15T00:00:00+00:00"),
        published_at="2026-02-15T00:00:00+00:00",
    )
    return ResearchResult(status="success", items=[item], sources=[item.source], retrieved_at="2026-03-01T00:00:00+00:00")


def _analyst():
    thesis = AnalystSection(text="Acme Corp shows strong profitability.", evidence=AnalystEvidence(financial=["roe"], research=["research_001"]))
    risk_section = AnalystSection(text="Leverage is a risk.", evidence=AnalystEvidence(risk=["high_debt_to_equity"]))
    valuation_section = AnalystSection(text="DCF suggests upside.", evidence=AnalystEvidence(valuation=["dcf"]))
    empty = AnalystSection(text="n/a")
    return AnalystResult(
        status="success",
        response=AnalystResponse(
            company_name="Acme Corp", investment_thesis=thesis,
            strengths=["Strong ROE"], weaknesses=["High leverage"],
            profitability_analysis=AnalystSection(text="Profitable.", evidence=AnalystEvidence(financial=["roe", "net_margin"])),
            growth_analysis=empty, financial_health_analysis=empty, cash_flow_analysis=empty,
            valuation_analysis=valuation_section, risk_analysis=risk_section,
            key_takeaways=["ROE is a strength"], caveats=["Limited periods available"],
        ),
    )


def _combined(**overrides) -> CombinedAnalysisResult:
    defaults = dict(
        company=PipelineCompanyInfo(name="Acme Corp", ticker="ACME"),
        status=PipelineStatus.CALCULATED,
        financial_analysis=_financial_analysis(),
        valuation=_valuation(),
        scoring=_scoring(),
        research=_research(),
        analyst=_analyst(),
        warnings=[],
        metadata=ExecutionMetadata(started_at="2026-03-01T00:00:00+00:00", completed_at="2026-03-01T00:00:05+00:00", duration_ms=5000),
    )
    defaults.update(overrides)
    return CombinedAnalysisResult(**defaults)


# --- Full / complete report ----------------------------------------------------------


def test_complete_report_status_and_metadata():
    report = ReportService(clock=_clock).generate(_combined())

    assert report.status is ReportStatus.CALCULATED
    assert report.company.name == "Acme Corp"
    assert report.company.ticker == "ACME"
    assert report.metadata.report_version == "1.0"
    assert report.metadata.generated_at == "2026-03-01T00:00:00+00:00"
    assert report.metadata.duration_ms == 5000


def test_complete_report_summary_uses_scoring_and_analyst_no_recalculation():
    report = ReportService(clock=_clock).generate(_combined())

    assert report.summary.overall_score == d(78)
    assert report.summary.score_band == "good"
    assert report.summary.investment_thesis == "Acme Corp shows strong profitability."
    assert report.summary.key_takeaways == ["ROE is a strength"]


def test_no_report_score_invented():
    # The report never adds a field that isn't already on ScoringResult.
    report = ReportService(clock=_clock).generate(_combined())
    assert not hasattr(report.summary, "report_score")
    assert not hasattr(report.summary, "confidence_score")


def test_financial_metrics_grouped_by_category_values_preserved():
    report = ReportService(clock=_clock).generate(_combined())
    fin = report.financials
    assert {m.name for m in fin.profitability} == {"roe", "net_margin"}
    # "fcf_growth" belongs to both Growth and Cash Flow scoring categories
    # upstream (Step 4); the report groups by first-match priority
    # (profitability, growth, financial_health, cash_flow), so it's shown
    # under Growth here.
    assert {m.name for m in fin.growth} == {"revenue_growth", "fcf_growth"}
    assert {m.name for m in fin.financial_health} == {"current_ratio"}
    assert {m.name for m in fin.cash_flow} == {"free_cash_flow"}
    roe = next(m for m in fin.profitability if m.name == "roe")
    assert roe.value == d(24)  # canonical value unchanged
    assert roe.formatted_value == "24.00%"


def test_unavailable_metric_not_converted_to_zero():
    report = ReportService(clock=_clock).generate(_combined())
    fcf_growth = next(m for m in report.financials.growth if m.name == "fcf_growth")
    assert fcf_growth.value is None
    assert fcf_growth.status == "unavailable"
    assert fcf_growth.formatted_value is None


def test_valuation_methods_preserved_independently_not_averaged():
    report = ReportService(clock=_clock).generate(_combined())
    methods = {m.method: m for m in report.valuation.methods}
    assert methods["dcf"].value_per_share == d(140)
    assert methods["dcf"].formatted_value_per_share == "$140.00"
    assert methods["dcf"].formatted_upside_downside == "40.00%"
    assert methods["pe"].value_per_share is None
    assert methods["pe"].status == "unavailable"
    # No composite/blended value exists anywhere on the section.
    assert not hasattr(report.valuation, "composite_value")
    assert not hasattr(report.valuation, "average_value")


def test_non_usd_currency_flows_from_company_into_formatted_values():
    # A company reporting in INR (e.g. an IndianAPI-sourced company) must
    # never have its monetary values silently rendered with a "$" prefix.
    combined = _combined(company=PipelineCompanyInfo(name="Acme India", ticker="ACME", currency="INR"))
    report = ReportService(clock=_clock).generate(combined)

    assert report.company.currency == "INR"
    fcf = next(m for m in report.financials.cash_flow if m.name == "free_cash_flow")
    assert fcf.formatted_value is not None and fcf.formatted_value.startswith("INR ")
    assert "$" not in fcf.formatted_value

    dcf = next(m for m in report.valuation.methods if m.method == "dcf")
    assert dcf.formatted_value_per_share.startswith("INR ")
    assert report.valuation.formatted_current_share_price.startswith("INR ")


def test_missing_currency_still_defaults_to_dollar_formatting():
    # Unchanged existing behavior when currency truly isn't known.
    report = ReportService(clock=_clock).generate(_combined())
    assert report.company.currency is None
    fcf = next(m for m in report.financials.cash_flow if m.name == "free_cash_flow")
    assert fcf.formatted_value.startswith("$")


def test_valuation_assumptions_exposed_not_invented():
    report = ReportService(clock=_clock).generate(_combined())
    dcf = next(m for m in report.valuation.methods if m.method == "dcf")
    assert dcf.assumptions["discount_rate"] == "0.09"
    pe = next(m for m in report.valuation.methods if m.method == "pe")
    assert pe.assumptions == {}  # unavailable method has no assumptions to show, none invented


def test_scoring_section_preserves_categories_and_components():
    report = ReportService(clock=_clock).generate(_combined())
    profitability = next(c for c in report.scoring.categories if c.category == "profitability")
    assert profitability.score == d(85)
    assert profitability.band == "strong"  # score_band(85) -- reused from Step 4, not recalculated
    assert profitability.components[0].name == "roe"
    valuation_cat = next(c for c in report.scoring.categories if c.category == "valuation")
    assert valuation_cat.status == "unavailable"
    assert valuation_cat.score is None


def test_risk_section_organized_by_severity_unaltered():
    report = ReportService(clock=_clock).generate(_combined())
    assert len(report.risk.high) == 1
    assert report.risk.high[0].name == "high_debt_to_equity"
    assert report.risk.high[0].severity == "high"
    assert len(report.risk.informational) == 1
    assert report.risk.informational[0].name == "negative_fcf"
    assert report.risk.critical == []


def test_research_section_preserves_attribution():
    report = ReportService(clock=_clock).generate(_combined())
    assert report.research.available is True
    item = report.research.items[0]
    assert item.id == "research_001"
    assert item.publisher == "Example News"
    assert item.url == "https://example.com/a"
    assert item.freshness in ("recent", "stale", "unknown")


def test_analyst_section_preserves_content_and_evidence():
    report = ReportService(clock=_clock).generate(_combined())
    assert report.analyst.available is True
    assert report.analyst.investment_thesis == "Acme Corp shows strong profitability."
    assert report.analyst.investment_thesis_evidence.financial == ["roe"]
    assert report.analyst.investment_thesis_evidence.research == ["research_001"]
    assert report.analyst.strengths == ["Strong ROE"]
    valuation_analysis = next(c for c in report.analyst.category_analysis if c.category == "valuation")
    assert valuation_analysis.evidence.valuation == ["dcf"]


def test_evidence_aggregated_across_sections():
    report = ReportService(clock=_clock).generate(_combined())
    assert "roe" in report.evidence.financial
    assert "net_margin" in report.evidence.financial
    assert "dcf" in report.evidence.valuation
    assert "high_debt_to_equity" in report.evidence.risk
    assert "research_001" in report.evidence.research


def test_no_buy_sell_hold_anywhere_in_report():
    report = ReportService(clock=_clock).generate(_combined())
    dumped = report.model_dump_json().lower()
    assert '"recommendation"' not in dumped
    assert '"buy"' not in dumped
    assert '"sell"' not in dumped
    assert '"hold"' not in dumped


def test_report_serializes_to_json_safely():
    report = ReportService(clock=_clock).generate(_combined())
    payload = report.model_dump_json()
    assert isinstance(payload, str)
    assert len(payload) > 0


# --- Partial / unavailable sections ---------------------------------------------------


def test_missing_analyst_result_marks_section_unavailable():
    combined = _combined(analyst=AnalystResult(status="error", error=AnalystError(code=AnalystErrorCode.TIMEOUT, message="timed out")), status=PipelineStatus.PARTIAL)
    report = ReportService(clock=_clock).generate(combined)

    assert report.status is ReportStatus.PARTIAL
    assert report.analyst.available is False
    assert report.summary.investment_thesis is None
    assert report.summary.key_takeaways == []


def test_missing_research_result_marks_section_unavailable():
    combined = _combined(research=None)
    report = ReportService(clock=_clock).generate(combined)

    assert report.research.available is False
    assert report.research.items == []


def test_research_error_status_marks_section_unavailable_not_crash():
    error_research = ResearchResult(status="error", error=ResearchError(code=ResearchErrorCode.PROVIDER_UNAVAILABLE, message="down"), retrieved_at="2026-03-01T00:00:00+00:00")
    combined = _combined(research=error_research)
    report = ReportService(clock=_clock).generate(combined)

    assert report.research.available is False
    assert any(w.source == "research" and w.code == "provider_unavailable" for w in report.warnings)


def test_missing_valuation_methods_handled():
    combined = _combined(valuation=ValuationRange(company="Acme Corp", results=[]))
    report = ReportService(clock=_clock).generate(combined)

    assert report.valuation.methods == []


def test_unavailable_scoring_categories_preserved_not_dropped():
    report = ReportService(clock=_clock).generate(_combined())
    categories = {c.category for c in report.scoring.categories}
    assert "valuation" in categories  # unavailable category still listed, not silently removed


def test_failed_pipeline_result_yields_failed_report_minimal_sections():
    combined = CombinedAnalysisResult(
        company=PipelineCompanyInfo(name="Acme Corp", ticker="ACME"),
        status=PipelineStatus.FAILED,
        warnings=["Pipeline failed during the financial_analysis stage."],
        metadata=ExecutionMetadata(started_at="2026-03-01T00:00:00+00:00", completed_at="2026-03-01T00:00:01+00:00", duration_ms=1000),
    )
    report = ReportService(clock=_clock).generate(combined)

    assert report.status is ReportStatus.FAILED
    assert report.financials is None
    assert report.valuation is None
    assert report.scoring is None
    assert any("financial_analysis" in w.message for w in report.warnings)


# --- Warnings / lineage ----------------------------------------------------------------


def test_warnings_propagate_from_all_sources_with_source_tag():
    report = ReportService(clock=_clock).generate(_combined())
    sources = {w.source for w in report.warnings}
    assert "financial_analysis" in sources
    assert "valuation" in sources
    assert "scoring" in sources


def test_section_source_lineage_tags_present():
    report = ReportService(clock=_clock).generate(_combined())
    assert report.financials.source == "financial_analysis"
    assert report.valuation.source == "valuation"
    assert report.scoring.source == "scoring"
    assert report.risk.source == "scoring"
    assert report.research.source == "research"
    assert report.analyst.source == "analyst"


# --- Deterministic assembly / injectable clock ------------------------------------------


def test_same_input_and_clock_produces_same_report():
    combined = _combined()
    report_a = ReportService(clock=_clock).generate(combined)
    report_b = ReportService(clock=_clock).generate(combined)
    assert report_a.model_dump_json() == report_b.model_dump_json()


def test_clock_is_injectable_and_used_for_generated_at():
    def fixed_clock():
        return datetime(2030, 1, 1, tzinfo=timezone.utc)

    report = ReportService(clock=fixed_clock).generate(_combined())
    assert report.metadata.generated_at == "2030-01-01T00:00:00+00:00"
