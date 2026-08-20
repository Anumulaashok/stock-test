"""Scoring service.

Wires a `FinancialAnalysisResult` (Step 2) and an optional
`ValuationRange` (Step 3) through every scoring category and the risk
engine, then combines category scores into an overall 0-100 score using
the same "renormalize over available categories" policy used within
each category. Never calls the LLM.
"""

from app.models.financial_results import FinancialAnalysisResult
from app.models.scoring import ScoringResult, ScoreStatus
from app.models.valuation import ValuationRange
from app.scoring.aggregation import aggregate_overall, metrics_by_name
from app.scoring.bands import score_band
from app.scoring.cash_flow import calculate_cash_flow_score
from app.scoring.financial_health import calculate_financial_health_score
from app.scoring.growth import calculate_growth_score
from app.scoring.profitability import calculate_profitability_score
from app.scoring.risk import calculate_risk_score, detect_risk_indicators
from app.scoring.thresholds import CATEGORY_WEIGHTS
from app.scoring.valuation import calculate_valuation_score


class ScoringService:
    """Runs the full deterministic scoring and risk engine."""

    def analyze(
        self, financials: FinancialAnalysisResult, valuation: ValuationRange | None = None
    ) -> ScoringResult:
        metrics = metrics_by_name(financials)

        category_scores = [
            calculate_profitability_score(metrics, CATEGORY_WEIGHTS["profitability"]),
            calculate_growth_score(metrics, CATEGORY_WEIGHTS["growth"]),
            calculate_financial_health_score(metrics, CATEGORY_WEIGHTS["financial_health"]),
            calculate_cash_flow_score(metrics, CATEGORY_WEIGHTS["cash_flow"]),
            calculate_valuation_score(valuation, CATEGORY_WEIGHTS["valuation"]),
        ]

        risk_indicators = detect_risk_indicators(metrics, valuation)
        risk_category = calculate_risk_score(risk_indicators, CATEGORY_WEIGHTS["risk"])
        category_scores.append(risk_category)

        overall_score, overall_status, warnings = aggregate_overall(category_scores)
        band = score_band(overall_score) if overall_status is ScoreStatus.CALCULATED else None

        return ScoringResult(
            company_name=financials.company,
            overall_score=overall_score,
            overall_status=overall_status,
            band=band,
            category_scores=category_scores,
            risk_indicators=risk_indicators,
            warnings=warnings,
        )
