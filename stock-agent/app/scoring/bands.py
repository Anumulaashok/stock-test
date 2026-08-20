"""Deterministic, descriptive score interpretation bands.

These are classifications only ("Excellent" .. "Poor") — they never map
to a buy/sell/hold recommendation, which belongs to a future decision
layer, not this scoring engine.
"""

from decimal import Decimal

from app.models.scoring import ScoreBand
from app.scoring.thresholds import SCORE_BAND_THRESHOLDS


def score_band(score: Decimal) -> ScoreBand:
    for threshold, band_name in SCORE_BAND_THRESHOLDS:
        if score >= threshold:
            return ScoreBand(band_name)
    return ScoreBand.POOR
