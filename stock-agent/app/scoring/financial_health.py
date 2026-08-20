"""Financial health category score.

Uses current ratio, cash ratio, debt/equity, debt/FCF, and interest
coverage. Current ratio uses the dedicated "sweet spot" normalization
(see `normalization.normalize_current_ratio`); the rest use linear
bands, lower-is-better for the two leverage ratios.
"""

from decimal import Decimal

from app.models.financial_results import FinancialMetricResult
from app.models.scoring import CategoryScore
from app.scoring.aggregation import aggregate_category, score_metric
from app.scoring.normalization import (
    normalize_current_ratio,
    normalize_linear_higher_is_better,
    normalize_linear_lower_is_better,
)
from app.scoring.thresholds import (
    CASH_RATIO_BAND,
    DEBT_TO_EQUITY_BAND,
    DEBT_TO_FCF_BAND,
    FINANCIAL_HEALTH_WEIGHTS,
    INTEREST_COVERAGE_BAND,
)


def calculate_financial_health_score(
    metrics: dict[str, FinancialMetricResult], category_weight: Decimal
) -> CategoryScore:
    components = [
        score_metric(metrics, "current_ratio", FINANCIAL_HEALTH_WEIGHTS["current_ratio"], normalize_current_ratio),
        score_metric(
            metrics, "cash_ratio", FINANCIAL_HEALTH_WEIGHTS["cash_ratio"],
            lambda v: normalize_linear_higher_is_better(v, CASH_RATIO_BAND),
        ),
        score_metric(
            metrics, "debt_to_equity", FINANCIAL_HEALTH_WEIGHTS["debt_to_equity"],
            lambda v: normalize_linear_lower_is_better(v, DEBT_TO_EQUITY_BAND),
        ),
        score_metric(
            metrics, "debt_to_fcf", FINANCIAL_HEALTH_WEIGHTS["debt_to_fcf"],
            lambda v: normalize_linear_lower_is_better(v, DEBT_TO_FCF_BAND),
        ),
        score_metric(
            metrics, "interest_coverage", FINANCIAL_HEALTH_WEIGHTS["interest_coverage"],
            lambda v: normalize_linear_higher_is_better(v, INTEREST_COVERAGE_BAND),
        ),
    ]
    return aggregate_category("financial_health", components, category_weight)
