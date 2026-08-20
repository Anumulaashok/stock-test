"""Builds the structured `AnalystContext` sent to the LLM.

This module only selects and reshapes fields already produced by the
deterministic engines (Steps 2-4) — it performs no calculation of its
own. Status values, reasons, and warnings are all preserved verbatim so
the model can see (and must respect) what is unavailable or invalid.
"""

from app.models.analyst import (
    AnalystCategoryScoreContext,
    AnalystCompanyContext,
    AnalystContext,
    AnalystMetricContext,
    AnalystRiskContext,
    AnalystValuationMethodContext,
)
from app.models.financial_results import FinancialAnalysisResult
from app.models.financial_statements import CompanyFinancials
from app.models.scoring import ScoringResult
from app.models.valuation import ValuationRange


def build_analyst_context(
    financial_analysis: FinancialAnalysisResult,
    valuation: ValuationRange | None,
    scoring: ScoringResult,
    company_financials: CompanyFinancials | None = None,
) -> AnalystContext:
    """Assemble the single, serializable context the LLM will see."""
    company = AnalystCompanyContext(
        name=financial_analysis.company,
        ticker=company_financials.ticker if company_financials else None,
    )

    financial_metrics = [
        AnalystMetricContext(
            name=metric.name, value=metric.value, unit=metric.unit,
            status=metric.status.value, reason=metric.reason,
        )
        for metric in financial_analysis.metrics
    ]

    current_share_price = valuation.current_share_price if valuation else None
    valuation_methods = [
        AnalystValuationMethodContext(
            method=result.method, value_per_share=result.value_per_share,
            status=result.status.value, reason=result.reason,
            upside_downside_percent=result.upside_downside_percent,
            upside_downside_status=(
                result.upside_downside_status.value if result.upside_downside_status else None
            ),
        )
        for result in (valuation.results if valuation else [])
    ]
    valuation_warnings = valuation.warnings if valuation else []

    category_scores = [
        AnalystCategoryScoreContext(
            category=category.category, score=category.score,
            status=category.status.value, reason=category.reason,
        )
        for category in scoring.category_scores
    ]
    risk_indicators = [
        AnalystRiskContext(
            name=risk.name, severity=risk.severity.value if risk.severity else None,
            status=risk.status.value, reason=risk.reason,
        )
        for risk in scoring.risk_indicators
    ]

    return AnalystContext(
        company=company,
        periods_analyzed=financial_analysis.periods_analyzed,
        financial_metrics=financial_metrics,
        financial_warnings=financial_analysis.warnings,
        current_share_price=current_share_price,
        valuation_methods=valuation_methods,
        valuation_warnings=valuation_warnings,
        overall_score=scoring.overall_score,
        overall_status=scoring.overall_status.value,
        band=scoring.band.value if scoring.band else None,
        category_scores=category_scores,
        risk_indicators=risk_indicators,
        scoring_warnings=scoring.warnings,
    )


def valid_evidence_names(context: AnalystContext) -> set[str]:
    """Every name the model is allowed to cite as evidence.

    Used by the response parser/validator to reject evidence references
    that don't correspond to anything actually supplied in the context.
    """
    names = {metric.name for metric in context.financial_metrics}
    names |= {method.method for method in context.valuation_methods}
    names |= {category.category for category in context.category_scores}
    names |= {risk.name for risk in context.risk_indicators}
    return names
