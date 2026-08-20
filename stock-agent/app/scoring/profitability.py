"""Profitability category score.

Uses whichever of gross/operating/net/FCF margin, ROE, ROA, and ROIC are
available from a `FinancialAnalysisResult`. Missing metrics reduce the
effective sample (via `aggregate_category`'s weight renormalization),
never treated as a zero.
"""

from decimal import Decimal

from app.models.financial_results import FinancialMetricResult
from app.models.scoring import CategoryScore
from app.scoring.aggregation import aggregate_category, score_metric
from app.scoring.normalization import normalize_linear_higher_is_better
from app.scoring.thresholds import (
    FCF_MARGIN_BAND,
    GROSS_MARGIN_BAND,
    NET_MARGIN_BAND,
    OPERATING_MARGIN_BAND,
    PROFITABILITY_WEIGHTS,
    ROA_BAND,
    ROE_BAND,
    ROIC_BAND,
)

_BANDS = {
    "gross_margin": GROSS_MARGIN_BAND,
    "operating_margin": OPERATING_MARGIN_BAND,
    "net_margin": NET_MARGIN_BAND,
    "fcf_margin": FCF_MARGIN_BAND,
    "roe": ROE_BAND,
    "roa": ROA_BAND,
    "roic": ROIC_BAND,
}


def calculate_profitability_score(
    metrics: dict[str, FinancialMetricResult], category_weight: Decimal
) -> CategoryScore:
    components = [
        score_metric(
            metrics, name, weight, lambda v, band=_BANDS[name]: normalize_linear_higher_is_better(v, band)
        )
        for name, weight in PROFITABILITY_WEIGHTS.items()
    ]
    return aggregate_category("profitability", components, category_weight)
