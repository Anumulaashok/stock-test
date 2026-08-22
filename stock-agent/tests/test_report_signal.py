from decimal import Decimal

from app.models.scoring import RiskIndicator, ScoreBand, ScoreStatus, ScoringResult, Severity
from app.reporting.signal import compute_signal


def d(value) -> Decimal:
    return Decimal(str(value))


def _scoring(band: ScoreBand, risk_indicators=None) -> ScoringResult:
    return ScoringResult(
        company_name="Acme Corp",
        overall_score=d(80),
        overall_status=ScoreStatus.CALCULATED,
        band=band,
        risk_indicators=risk_indicators or [],
    )


def _risk(severity: Severity | None, status: ScoreStatus = ScoreStatus.CALCULATED) -> RiskIndicator:
    return RiskIndicator(name="test_risk", severity=severity, status=status, reason="test")


def test_no_scoring_result_is_unavailable():
    signal = compute_signal(None)
    assert signal.label == "unavailable"
    assert signal.color == "gray"


def test_missing_band_is_unavailable():
    scoring = ScoringResult(
        company_name="Acme Corp", overall_score=None, overall_status=ScoreStatus.UNAVAILABLE, band=None
    )
    signal = compute_signal(scoring)
    assert signal.label == "unavailable"
    assert signal.color == "gray"


def test_good_band_with_no_risk_is_green():
    signal = compute_signal(_scoring(ScoreBand.GOOD))
    assert signal.color == "green"
    assert signal.label == "strong"


def test_excellent_band_with_low_risk_is_still_green():
    signal = compute_signal(_scoring(ScoreBand.EXCELLENT, [_risk(Severity.LOW)]))
    assert signal.color == "green"


def test_good_band_with_high_risk_downgrades_to_yellow():
    signal = compute_signal(_scoring(ScoreBand.GOOD, [_risk(Severity.HIGH)]))
    assert signal.color == "yellow"
    assert signal.label == "moderate"


def test_good_band_with_critical_risk_downgrades_to_red():
    signal = compute_signal(_scoring(ScoreBand.GOOD, [_risk(Severity.CRITICAL)]))
    assert signal.color == "red"
    assert signal.label == "weak"


def test_fair_band_with_no_high_risk_is_yellow():
    signal = compute_signal(_scoring(ScoreBand.FAIR, [_risk(Severity.MEDIUM)]))
    assert signal.color == "yellow"


def test_fair_band_with_high_risk_is_red():
    signal = compute_signal(_scoring(ScoreBand.FAIR, [_risk(Severity.HIGH)]))
    assert signal.color == "red"


def test_weak_band_is_red_regardless_of_risk():
    signal = compute_signal(_scoring(ScoreBand.WEAK))
    assert signal.color == "red"


def test_poor_band_is_red():
    signal = compute_signal(_scoring(ScoreBand.POOR))
    assert signal.color == "red"


def test_unavailable_risk_indicator_is_ignored():
    signal = compute_signal(
        _scoring(ScoreBand.GOOD, [_risk(Severity.CRITICAL, status=ScoreStatus.UNAVAILABLE)])
    )
    assert signal.color == "green"
