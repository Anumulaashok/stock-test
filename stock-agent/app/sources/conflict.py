"""Deterministic resolution when two sources report the same metric.

Values are never averaged: an average of two disagreeing sources is a
number no source actually reported. The primary source wins, and the
disagreement is recorded so it can be investigated.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.sources.periods import normalize_period, same_period
from app.sources.units import CanonicalUnit, UnitConversionError, to_base

# Providers rounding to different precisions routinely differ in the
# fourth significant figure; that is not a conflict worth flagging.
DEFAULT_TOLERANCE = Decimal("0.01")


class ConflictStatus(StrEnum):
    SINGLE_SOURCE = "SINGLE_SOURCE"
    AGREEMENT = "AGREEMENT"
    CONFLICT = "CONFLICT"
    INCOMPARABLE = "INCOMPARABLE"


class Resolution(StrEnum):
    PRIMARY_SOURCE_SELECTED = "PRIMARY_SOURCE_SELECTED"
    ONLY_OBSERVATION = "ONLY_OBSERVATION"
    NO_OBSERVATIONS = "NO_OBSERVATIONS"


class MetricObservation(BaseModel):
    """One source's reading of one metric for one period."""

    metric: str
    value: Decimal
    unit: CanonicalUnit
    period: str | None = None
    source: str


class MetricResolution(BaseModel):
    metric: str
    period: str | None = None
    observations: list[MetricObservation] = Field(default_factory=list)
    status: ConflictStatus
    resolution: Resolution
    selected: MetricObservation | None = None
    confidence: float = 1.0
    reason: str | None = None


def _relative_difference(left: MetricObservation, right: MetricObservation) -> Decimal | None:
    """Compare in each family's base unit. Returns None when the two
    readings are not comparable at all (incompatible units)."""
    try:
        a, b = to_base(left.value, left.unit), to_base(right.value, right.unit)
    except UnitConversionError:
        return None
    if a == 0 and b == 0:
        return Decimal(0)
    denominator = max(abs(a), abs(b))
    if denominator == 0:
        return Decimal(0)
    return abs(a - b) / denominator


def resolve_observations(
    observations: list[MetricObservation],
    *,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> MetricResolution:
    """`observations` must be ordered by provider priority — index 0 is
    the primary source and always wins."""
    if not observations:
        return MetricResolution(
            metric="",
            status=ConflictStatus.SINGLE_SOURCE,
            resolution=Resolution.NO_OBSERVATIONS,
            reason="no source returned this metric",
        )

    primary = observations[0]
    period_label = normalize_period(primary.period).label if primary.period else None

    if len(observations) == 1:
        return MetricResolution(
            metric=primary.metric,
            period=period_label,
            observations=observations,
            status=ConflictStatus.SINGLE_SOURCE,
            resolution=Resolution.ONLY_OBSERVATION,
            selected=primary,
            confidence=1.0,
            reason=f"only {primary.source} reported this metric",
        )

    comparable = [o for o in observations[1:] if same_period(primary.period, o.period)]
    if not comparable:
        return MetricResolution(
            metric=primary.metric,
            period=period_label,
            observations=observations,
            status=ConflictStatus.INCOMPARABLE,
            resolution=Resolution.PRIMARY_SOURCE_SELECTED,
            selected=primary,
            confidence=0.9,
            reason="secondary observations cover different periods; not compared",
        )

    differences = [(o, _relative_difference(primary, o)) for o in comparable]
    if any(diff is None for _, diff in differences):
        return MetricResolution(
            metric=primary.metric,
            period=period_label,
            observations=observations,
            status=ConflictStatus.INCOMPARABLE,
            resolution=Resolution.PRIMARY_SOURCE_SELECTED,
            selected=primary,
            confidence=0.9,
            reason="incompatible units between sources; not compared",
        )

    worst = max(differences, key=lambda pair: pair[1])
    worst_obs, worst_diff = worst[0], worst[1]

    if worst_diff <= tolerance:
        return MetricResolution(
            metric=primary.metric,
            period=period_label,
            observations=observations,
            status=ConflictStatus.AGREEMENT,
            resolution=Resolution.PRIMARY_SOURCE_SELECTED,
            selected=primary,
            confidence=1.0,
            reason=(
                f"sources agree within tolerance (max difference "
                f"{worst_diff:.4%} vs {worst_obs.source})"
            ),
        )

    return MetricResolution(
        metric=primary.metric,
        period=period_label,
        observations=observations,
        status=ConflictStatus.CONFLICT,
        resolution=Resolution.PRIMARY_SOURCE_SELECTED,
        selected=primary,
        confidence=0.5,
        reason=(
            f"{primary.source} and {worst_obs.source} differ by {worst_diff:.4%}, "
            f"beyond the {tolerance:.2%} tolerance; primary source used unchanged. "
            "Check period alignment and standalone-vs-consolidated basis."
        ),
    )
