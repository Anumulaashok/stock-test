"""Cash flow category score.

Uses free cash flow (sign only — raw dollar magnitude isn't comparable
across companies of different size), FCF margin, and FCF growth.
Negative FCF lowers the score but never raises an error.
"""

from decimal import Decimal

from app.models.financial_results import FinancialMetricResult
from app.models.scoring import CategoryScore
from app.scoring.aggregation import aggregate_category, score_metric
from app.scoring.normalization import normalize_linear_higher_is_better
from app.scoring.thresholds import (
    CASH_FLOW_WEIGHTS,
    FCF_GROWTH_BAND,
    FCF_MARGIN_BAND,
    FCF_SIGN_NEGATIVE_SCORE,
    FCF_SIGN_POSITIVE_SCORE,
    FCF_SIGN_ZERO_SCORE,
)


def _normalize_fcf_sign(value: Decimal) -> Decimal:
    if value > 0:
        return FCF_SIGN_POSITIVE_SCORE
    if value == 0:
        return FCF_SIGN_ZERO_SCORE
    return FCF_SIGN_NEGATIVE_SCORE


def calculate_cash_flow_score(
    metrics: dict[str, FinancialMetricResult], category_weight: Decimal
) -> CategoryScore:
    components = [
        score_metric(
            metrics, "free_cash_flow", CASH_FLOW_WEIGHTS["free_cash_flow"], _normalize_fcf_sign,
            display_name="free cash flow (sign)",
        ),
        score_metric(
            metrics, "fcf_margin", CASH_FLOW_WEIGHTS["fcf_margin"],
            lambda v: normalize_linear_higher_is_better(v, FCF_MARGIN_BAND),
        ),
        score_metric(
            metrics, "fcf_growth", CASH_FLOW_WEIGHTS["fcf_growth"],
            lambda v: normalize_linear_higher_is_better(v, FCF_GROWTH_BAND),
        ),
    ]
    return aggregate_category("cash_flow", components, category_weight)
