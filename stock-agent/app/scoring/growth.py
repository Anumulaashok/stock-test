"""Growth category score.

Uses whichever of revenue/net income/EPS/FCF growth are available.
Each is capped by its band's target (see `thresholds.py`), so a single
extreme growth number cannot dominate the category.
"""

from decimal import Decimal

from app.models.financial_results import FinancialMetricResult
from app.models.scoring import CategoryScore
from app.scoring.aggregation import aggregate_category, score_metric
from app.scoring.normalization import normalize_linear_higher_is_better
from app.scoring.thresholds import (
    EPS_GROWTH_BAND,
    FCF_GROWTH_BAND,
    GROWTH_WEIGHTS,
    NET_INCOME_GROWTH_BAND,
    REVENUE_GROWTH_BAND,
)

_BANDS = {
    "revenue_growth": REVENUE_GROWTH_BAND,
    "net_income_growth": NET_INCOME_GROWTH_BAND,
    "eps_growth": EPS_GROWTH_BAND,
    "fcf_growth": FCF_GROWTH_BAND,
}


def calculate_growth_score(
    metrics: dict[str, FinancialMetricResult], category_weight: Decimal
) -> CategoryScore:
    components = [
        score_metric(
            metrics, name, weight, lambda v, band=_BANDS[name]: normalize_linear_higher_is_better(v, band)
        )
        for name, weight in GROWTH_WEIGHTS.items()
    ]
    return aggregate_category("growth", components, category_weight)
