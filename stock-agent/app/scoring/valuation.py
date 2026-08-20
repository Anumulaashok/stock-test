"""Valuation category score.

Consumes a `ValuationRange` (Step 3) and scores each method's
upside/downside against the current market price independently —
methods are explicitly weighted, never averaged together before
scoring, and each stays individually visible in `components`.
"""

from decimal import Decimal

from app.models.financial_results import MetricStatus
from app.models.scoring import CategoryScore, ScoreComponent, ScoreStatus
from app.models.valuation import ValuationRange, ValuationResult
from app.scoring.aggregation import aggregate_category
from app.scoring.normalization import explain_score, normalize_linear_higher_is_better
from app.scoring.thresholds import VALUATION_METHOD_WEIGHTS, VALUATION_UPSIDE_BAND


def _score_method(result: ValuationResult, weight: Decimal) -> ScoreComponent:
    label = f"{result.method} upside/downside"

    if result.status is MetricStatus.UNAVAILABLE:
        return ScoreComponent(
            name=result.method, score=None, weight=weight, status=ScoreStatus.UNAVAILABLE,
            reason=result.reason, source_metric=result.method,
        )
    if result.status is MetricStatus.INVALID:
        return ScoreComponent(
            name=result.method, score=None, weight=weight, status=ScoreStatus.INVALID,
            reason=result.reason, source_metric=result.method,
        )

    if result.upside_downside_status is not MetricStatus.CALCULATED:
        reason = result.upside_downside_reason or (
            f"current share price is unavailable; cannot assess {label}"
        )
        status = (
            ScoreStatus.INVALID
            if result.upside_downside_status is MetricStatus.INVALID
            else ScoreStatus.UNAVAILABLE
        )
        return ScoreComponent(
            name=result.method, score=None, weight=weight, status=status,
            reason=reason, source_metric=result.method,
        )

    score = normalize_linear_higher_is_better(result.upside_downside_percent, VALUATION_UPSIDE_BAND)
    return ScoreComponent(
        name=result.method, score=score, weight=weight, status=ScoreStatus.CALCULATED,
        reason=explain_score(label, score), source_metric=result.method,
        value=result.upside_downside_percent,
    )


def calculate_valuation_score(
    valuation: ValuationRange | None, category_weight: Decimal
) -> CategoryScore:
    if valuation is None or not valuation.results:
        return CategoryScore(
            category="valuation", score=None, weight=category_weight,
            status=ScoreStatus.UNAVAILABLE, reason="No valuation data was provided.",
        )

    results_by_method = {result.method: result for result in valuation.results}
    components = [
        _score_method(results_by_method[method], weight)
        for method, weight in VALUATION_METHOD_WEIGHTS.items()
        if method in results_by_method
    ]

    if not components:
        return CategoryScore(
            category="valuation", score=None, weight=category_weight,
            status=ScoreStatus.UNAVAILABLE,
            reason="None of the configured valuation methods were present in the valuation data.",
        )

    return aggregate_category("valuation", components, category_weight)
