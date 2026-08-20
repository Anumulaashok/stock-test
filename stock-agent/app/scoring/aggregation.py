"""Shared building blocks for turning metrics into scores.

`score_metric` looks up one named metric and turns it into a
`ScoreComponent`, propagating unavailable/invalid status rather than
treating a missing metric as zero. `aggregate_category` and
`aggregate_overall` both implement the same policy: average only the
available (calculated) items, weighted by their *nominal* weight
renormalized over just those available items — so a missing input
lowers the sample size, not the score.
"""

from collections.abc import Callable
from decimal import Decimal

from app.models.financial_results import FinancialAnalysisResult, FinancialMetricResult
from app.models.financial_results import MetricStatus as FinancialMetricStatus
from app.models.scoring import CategoryScore, ScoreComponent, ScoreStatus
from app.scoring.normalization import explain_score


def metrics_by_name(financials: FinancialAnalysisResult) -> dict[str, FinancialMetricResult]:
    """Index a `FinancialAnalysisResult`'s metrics by name for lookup."""
    return {metric.name: metric for metric in financials.metrics}


def score_metric(
    metrics: dict[str, FinancialMetricResult],
    metric_name: str,
    weight: Decimal,
    normalizer: Callable[[Decimal], Decimal],
    display_name: str | None = None,
) -> ScoreComponent:
    """Build a `ScoreComponent` from a named metric, or report why it can't be scored."""
    label = display_name or metric_name.replace("_", " ")
    metric = metrics.get(metric_name)

    if metric is None:
        return ScoreComponent(
            name=metric_name, score=None, weight=weight, status=ScoreStatus.UNAVAILABLE,
            reason=f"{label} metric was not provided", source_metric=metric_name,
        )
    if metric.status is FinancialMetricStatus.UNAVAILABLE:
        return ScoreComponent(
            name=metric_name, score=None, weight=weight, status=ScoreStatus.UNAVAILABLE,
            reason=metric.reason, source_metric=metric_name,
        )
    if metric.status is FinancialMetricStatus.INVALID:
        return ScoreComponent(
            name=metric_name, score=None, weight=weight, status=ScoreStatus.INVALID,
            reason=metric.reason, source_metric=metric_name,
        )

    score = normalizer(metric.value)
    return ScoreComponent(
        name=metric_name, score=score, weight=weight, status=ScoreStatus.CALCULATED,
        reason=explain_score(label, score), source_metric=metric_name, value=metric.value,
    )


def _weighted_average(scored: list[tuple[Decimal, Decimal]]) -> Decimal | None:
    """`scored` is a list of (score, weight) pairs for available items only."""
    total_weight = sum(weight for _, weight in scored)
    if total_weight == 0:
        return None
    return sum(score * weight for score, weight in scored) / total_weight


def aggregate_category(
    category_name: str, components: list[ScoreComponent], nominal_weight: Decimal
) -> CategoryScore:
    """Aggregate a category's components into a single 0-100 score.

    Only CALCULATED components contribute; their weights are
    renormalized against each other so missing inputs shrink the
    effective sample rather than dragging the score toward zero.
    """
    available = [c for c in components if c.status == ScoreStatus.CALCULATED]

    if not available:
        return CategoryScore(
            category=category_name, score=None, weight=nominal_weight,
            status=ScoreStatus.UNAVAILABLE,
            reason=f"No {category_name.replace('_', ' ')} metrics were available to score.",
            components=components,
        )

    score = _weighted_average([(c.score, c.weight) for c in available])
    reason = None
    if len(available) < len(components):
        missing = [c.name for c in components if c.status != ScoreStatus.CALCULATED]
        reason = (
            f"Used {len(available)} of {len(components)} metrics "
            f"(missing: {', '.join(missing)})."
        )

    return CategoryScore(
        category=category_name, score=score, weight=nominal_weight,
        status=ScoreStatus.CALCULATED, reason=reason, components=components,
    )


def aggregate_overall(
    category_scores: list[CategoryScore],
) -> tuple[Decimal | None, ScoreStatus, list[str]]:
    """Aggregate category scores into the overall score, same renormalization policy."""
    available = [c for c in category_scores if c.status == ScoreStatus.CALCULATED]
    warnings: list[str] = []

    unavailable = [c for c in category_scores if c.status != ScoreStatus.CALCULATED]
    for category in unavailable:
        warnings.append(
            f"{category.category.replace('_', ' ').title()} category was "
            f"{category.status.value} and excluded from the overall score."
        )
    for category in available:
        if category.reason:
            warnings.append(f"{category.category.replace('_', ' ').title()}: {category.reason}")

    if not available:
        return None, ScoreStatus.UNAVAILABLE, warnings + [
            "No category scores were available; overall score is unavailable."
        ]

    overall = _weighted_average([(c.score, c.weight) for c in available])
    return overall, ScoreStatus.CALCULATED, warnings
