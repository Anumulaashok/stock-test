"""Derives a deterministic, color-coded strength signal from an
already-computed `ScoringResult`.

This is explicitly NOT a buy/sell/hold recommendation. `app/scoring/
bands.py` deliberately keeps score bands descriptive-only and defers
any decision-layer interpretation to "a future decision layer, not this
scoring engine" — this module is that layer, and it stays within the
same boundary: it recolors `overall_score`'s band and the risk
indicators that already exist, it never computes a new number, and it
never outputs "buy", "sell", or "hold".

Green/yellow/red reflects how strong the company's deterministic
fundamentals and risk profile look as data — not a prediction, and not
advice.
"""

from app.models.report import ReportSignal
from app.models.scoring import ScoreBand, ScoreStatus, ScoringResult, Severity

_GREEN_BANDS = {ScoreBand.EXCELLENT, ScoreBand.STRONG, ScoreBand.GOOD}
_YELLOW_BANDS = {ScoreBand.FAIR}
# Everything else (WEAK, POOR) is treated as red.

_SEVERITY_RANK = (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW)


def _worst_severity(scoring: ScoringResult) -> Severity | None:
    present = {
        risk.severity
        for risk in scoring.risk_indicators
        if risk.status == ScoreStatus.CALCULATED and risk.severity is not None
    }
    for level in _SEVERITY_RANK:
        if level in present:
            return level
    return None


def compute_signal(scoring: ScoringResult | None) -> ReportSignal:
    """Never fabricates a signal for missing data — an unscored company
    gets `label="unavailable"`, never a guessed color."""
    if scoring is None or scoring.band is None or scoring.overall_score is None:
        return ReportSignal(
            label="unavailable",
            color="gray",
            reason="Not enough deterministic data was available to compute an overall score.",
        )

    band = scoring.band
    worst = _worst_severity(scoring)

    if band in _GREEN_BANDS:
        if worst == Severity.CRITICAL:
            return ReportSignal(
                label="weak",
                color="red",
                reason=f"Overall score is {band.value}, but a critical-severity risk indicator was flagged.",
            )
        if worst == Severity.HIGH:
            return ReportSignal(
                label="moderate",
                color="yellow",
                reason=f"Overall score is {band.value}, but a high-severity risk indicator was flagged.",
            )
        return ReportSignal(
            label="strong",
            color="green",
            reason=f"Overall score is {band.value} with no high-severity risk indicators.",
        )

    if band in _YELLOW_BANDS:
        if worst in (Severity.CRITICAL, Severity.HIGH):
            return ReportSignal(
                label="weak",
                color="red",
                reason=f"Overall score is {band.value} and a {worst.value}-severity risk indicator was flagged.",
            )
        return ReportSignal(
            label="moderate",
            color="yellow",
            reason=f"Overall score is {band.value}.",
        )

    return ReportSignal(
        label="weak",
        color="red",
        reason=f"Overall score is {band.value}.",
    )
