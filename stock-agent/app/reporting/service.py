"""Deterministic report assembly.

`ReportService.generate` turns an already-computed `CombinedAnalysisResult`
into a structured `InvestmentResearchReport`. It performs no financial
calculation, no re-scoring, no re-valuation, no re-interpretation of
risk, and never calls the LLM or any external provider — it only
reshapes and formats results that Steps 2-8 already produced. Same
input + same clock => same report.
"""

from collections.abc import Callable
from datetime import datetime, timezone

from app.models.analyst import AnalystEvidence, AnalystResult
from app.models.financial_results import FinancialAnalysisResult
from app.models.report import (
    InvestmentResearchReport,
    ReportAnalystCategoryAnalysis,
    ReportAnalystSection,
    ReportCategoryScore,
    ReportCompany,
    ReportEvidence,
    ReportFinancialMetric,
    ReportFinancialSection,
    ReportMetadata,
    ReportResearchItem,
    ReportResearchSection,
    ReportRiskIndicator,
    ReportRiskSection,
    ReportScoreComponent,
    ReportScoringSection,
    ReportStatus,
    ReportSummary,
    ReportValuationMethod,
    ReportValuationSection,
    ReportWarning,
)
from app.models.research import ResearchResult
from app.models.scoring import ScoringResult, Severity
from app.models.valuation import ValuationRange
from app.pipeline.models import CombinedAnalysisResult, PipelineStatus
from app.reporting.constants import REPORT_VERSION
from app.reporting.evidence import filter_evidence, valid_report_evidence_names
from app.reporting.formatter import format_currency, format_metric_value, format_percent
from app.reporting.warnings import collect_warnings
from app.scoring.bands import score_band
from app.scoring.thresholds import (
    CASH_FLOW_WEIGHTS,
    FINANCIAL_HEALTH_WEIGHTS,
    GROWTH_WEIGHTS,
    PROFITABILITY_WEIGHTS,
)

_SEVERITY_BUCKETS = {
    Severity.CRITICAL: "critical",
    Severity.HIGH: "high",
    Severity.MEDIUM: "medium",
    Severity.LOW: "low",
}


class ReportService:
    """Has no dependency on any LLM/provider — only an optional injectable
    clock, so `generated_at` stays deterministic in tests."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def generate(self, combined: CombinedAnalysisResult) -> InvestmentResearchReport:
        generated_at = self._clock().isoformat()
        company = ReportCompany(name=combined.company.name, ticker=combined.company.ticker)
        metadata = self._build_metadata(combined, generated_at)

        if combined.status is PipelineStatus.FAILED or combined.financial_analysis is None:
            return InvestmentResearchReport(
                company=company, status=ReportStatus.FAILED,
                summary=ReportSummary(),
                warnings=collect_warnings(combined),
                metadata=metadata,
            )

        valid_evidence = valid_report_evidence_names(
            combined.financial_analysis, combined.valuation, combined.scoring, combined.research
        )

        financials_section = self._build_financial_section(combined.financial_analysis)
        valuation_section = (
            self._build_valuation_section(combined.valuation) if combined.valuation else None
        )
        scoring_section = self._build_scoring_section(combined.scoring) if combined.scoring else None
        risk_section = self._build_risk_section(combined.scoring) if combined.scoring else None
        research_section = self._build_research_section(combined.research)
        analyst_section, evidence_warnings = self._build_analyst_section(
            combined.analyst, valid_evidence
        )

        summary = self._build_summary(combined.scoring, combined.analyst)
        evidence = self._aggregate_evidence(analyst_section)
        warnings = collect_warnings(combined) + [
            ReportWarning(source="report", message=message) for message in evidence_warnings
        ]

        return InvestmentResearchReport(
            company=company,
            status=ReportStatus(combined.status.value),
            summary=summary,
            financials=financials_section,
            valuation=valuation_section,
            scoring=scoring_section,
            risk=risk_section,
            research=research_section,
            analyst=analyst_section,
            evidence=evidence,
            warnings=warnings,
            metadata=metadata,
        )

    # --- section builders -------------------------------------------------------

    def _build_metadata(self, combined: CombinedAnalysisResult, generated_at: str) -> ReportMetadata:
        return ReportMetadata(
            report_version=REPORT_VERSION,
            generated_at=generated_at,
            pipeline_version=combined.metadata.pipeline_version if combined.metadata else None,
            duration_ms=combined.metadata.duration_ms if combined.metadata else None,
        )

    def _build_summary(
        self, scoring: ScoringResult | None, analyst: AnalystResult | None
    ) -> ReportSummary:
        thesis = None
        takeaways: list[str] = []
        if analyst and analyst.status == "success" and analyst.response:
            thesis = analyst.response.investment_thesis.text
            takeaways = analyst.response.key_takeaways

        return ReportSummary(
            overall_score=scoring.overall_score if scoring else None,
            overall_status=scoring.overall_status.value if scoring else "unavailable",
            score_band=scoring.band.value if scoring and scoring.band else None,
            investment_thesis=thesis,
            key_takeaways=takeaways,
        )

    def _build_financial_section(self, fa: FinancialAnalysisResult) -> ReportFinancialSection:
        buckets: dict[str, list[ReportFinancialMetric]] = {
            "profitability": [], "growth": [], "financial_health": [], "cash_flow": [], "other": [],
        }
        for metric in fa.metrics:
            report_metric = ReportFinancialMetric(
                name=metric.name, value=metric.value, unit=metric.unit,
                status=metric.status.value, reason=metric.reason,
                source_periods=metric.source_periods,
                formatted_value=format_metric_value(metric.value, metric.unit),
            )
            if metric.name in PROFITABILITY_WEIGHTS:
                buckets["profitability"].append(report_metric)
            elif metric.name in GROWTH_WEIGHTS:
                buckets["growth"].append(report_metric)
            elif metric.name in FINANCIAL_HEALTH_WEIGHTS:
                buckets["financial_health"].append(report_metric)
            elif metric.name in CASH_FLOW_WEIGHTS:
                buckets["cash_flow"].append(report_metric)
            else:
                buckets["other"].append(report_metric)

        return ReportFinancialSection(periods_analyzed=fa.periods_analyzed, **buckets)

    def _build_valuation_section(self, valuation: ValuationRange) -> ReportValuationSection:
        methods = [
            ReportValuationMethod(
                method=result.method, value_per_share=result.value_per_share,
                status=result.status.value, reason=result.reason,
                upside_downside_percent=result.upside_downside_percent,
                upside_downside_status=(
                    result.upside_downside_status.value if result.upside_downside_status else None
                ),
                assumptions={k: str(v) for k, v in result.assumptions.items()},
                formatted_value_per_share=format_currency(result.value_per_share),
                formatted_upside_downside=format_percent(result.upside_downside_percent),
            )
            for result in valuation.results
        ]
        return ReportValuationSection(
            current_share_price=valuation.current_share_price,
            formatted_current_share_price=format_currency(valuation.current_share_price),
            methods=methods,
        )

    def _build_scoring_section(self, scoring: ScoringResult) -> ReportScoringSection:
        categories = [
            ReportCategoryScore(
                category=category.category, score=category.score, weight=category.weight,
                status=category.status.value,
                band=score_band(category.score).value if category.score is not None else None,
                reason=category.reason,
                components=[
                    ReportScoreComponent(
                        name=component.name, score=component.score, weight=component.weight,
                        status=component.status.value, reason=component.reason,
                    )
                    for component in category.components
                ],
            )
            for category in scoring.category_scores
        ]
        return ReportScoringSection(
            overall_score=scoring.overall_score, overall_status=scoring.overall_status.value,
            band=scoring.band.value if scoring.band else None, categories=categories,
        )

    def _build_risk_section(self, scoring: ScoringResult) -> ReportRiskSection:
        buckets: dict[str, list[ReportRiskIndicator]] = {
            "critical": [], "high": [], "medium": [], "low": [], "informational": [],
        }
        for indicator in scoring.risk_indicators:
            report_indicator = ReportRiskIndicator(
                name=indicator.name, severity=indicator.severity.value if indicator.severity else None,
                status=indicator.status.value, value=indicator.value, threshold=indicator.threshold,
                reason=indicator.reason,
            )
            bucket = _SEVERITY_BUCKETS.get(indicator.severity, "informational")
            buckets[bucket].append(report_indicator)
        return ReportRiskSection(**buckets)

    def _build_research_section(self, research: ResearchResult | None) -> ReportResearchSection:
        if research is None or research.status != "success":
            return ReportResearchSection(available=False)
        items = [
            ReportResearchItem(
                id=item.id, title=item.title, publisher=item.source.publisher,
                published_at=item.published_at, freshness=item.freshness.value,
                relevance=item.relevance, summary=item.summary, url=item.source.url,
                source_type=item.source.source_type.value,
            )
            for item in research.items
        ]
        return ReportResearchSection(available=True, items=items)

    def _build_analyst_section(
        self, analyst: AnalystResult | None, valid_evidence: dict[str, set[str]]
    ) -> tuple[ReportAnalystSection, list[str]]:
        if analyst is None or analyst.status != "success" or analyst.response is None:
            return ReportAnalystSection(available=False), []

        response = analyst.response
        warnings: list[str] = []

        def filtered(label: str, evidence: AnalystEvidence) -> AnalystEvidence:
            result, section_warnings = filter_evidence(evidence, valid_evidence)
            warnings.extend(f"{label}: {w}" for w in section_warnings)
            return result

        thesis_evidence = filtered("investment_thesis", response.investment_thesis.evidence)
        category_sections = [
            ("profitability", response.profitability_analysis),
            ("growth", response.growth_analysis),
            ("financial_health", response.financial_health_analysis),
            ("cash_flow", response.cash_flow_analysis),
            ("valuation", response.valuation_analysis),
            ("risk", response.risk_analysis),
        ]
        category_analysis = [
            ReportAnalystCategoryAnalysis(
                category=name, text=section.text, evidence=filtered(name, section.evidence)
            )
            for name, section in category_sections
        ]

        return (
            ReportAnalystSection(
                available=True,
                investment_thesis=response.investment_thesis.text,
                investment_thesis_evidence=thesis_evidence,
                strengths=response.strengths, weaknesses=response.weaknesses,
                category_analysis=category_analysis,
                key_takeaways=response.key_takeaways, caveats=response.caveats,
            ),
            warnings,
        )

    def _aggregate_evidence(self, analyst_section: ReportAnalystSection) -> ReportEvidence:
        financial: set[str] = set()
        valuation: set[str] = set()
        risk: set[str] = set()
        research: set[str] = set()

        evidences = []
        if analyst_section.available:
            if analyst_section.investment_thesis_evidence:
                evidences.append(analyst_section.investment_thesis_evidence)
            evidences.extend(c.evidence for c in analyst_section.category_analysis)

        for evidence in evidences:
            financial |= set(evidence.financial)
            valuation |= set(evidence.valuation)
            risk |= set(evidence.risk)
            research |= set(evidence.research)

        return ReportEvidence(
            financial=sorted(financial), valuation=sorted(valuation),
            risk=sorted(risk), research=sorted(research),
        )
