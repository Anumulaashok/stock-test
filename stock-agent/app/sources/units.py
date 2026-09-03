"""Canonical units.

Provider adapters normalize into these before any value is compared or
stored. Comparing raw provider values without normalization is how a
0.016% difference and a 100x unit mismatch become indistinguishable.
"""

from decimal import Decimal
from enum import StrEnum


class CanonicalUnit(StrEnum):
    INR = "INR"
    INR_CRORE = "INR_CRORE"
    INR_MILLION = "INR_MILLION"
    PERCENT = "PERCENT"
    RATIO = "RATIO"
    SHARES = "SHARES"


class UnitConversionError(ValueError):
    """Raised when a conversion between incompatible units is attempted —
    never silently returns the input unconverted."""


# Everything monetary is expressed relative to one plain INR.
_INR_SCALE: dict[CanonicalUnit, Decimal] = {
    CanonicalUnit.INR: Decimal(1),
    CanonicalUnit.INR_MILLION: Decimal(1_000_000),
    CanonicalUnit.INR_CRORE: Decimal(10_000_000),
}

_DIMENSIONLESS: dict[CanonicalUnit, Decimal] = {
    CanonicalUnit.RATIO: Decimal(1),
    CanonicalUnit.PERCENT: Decimal("0.01"),
}


def convert(value: Decimal, source: CanonicalUnit, target: CanonicalUnit) -> Decimal:
    """Convert between two units in the same family."""
    if source == target:
        return value
    for family in (_INR_SCALE, _DIMENSIONLESS):
        if source in family and target in family:
            return value * family[source] / family[target]
    if source == CanonicalUnit.SHARES or target == CanonicalUnit.SHARES:
        raise UnitConversionError(f"cannot convert {source} to {target}: share counts are not scalable")
    raise UnitConversionError(f"cannot convert {source} to {target}: incompatible unit families")


def to_base(value: Decimal, unit: CanonicalUnit) -> Decimal:
    """Normalize to the family's base unit (INR, or RATIO) for comparison."""
    if unit in _INR_SCALE:
        return convert(value, unit, CanonicalUnit.INR)
    if unit in _DIMENSIONLESS:
        return convert(value, unit, CanonicalUnit.RATIO)
    return value
