"""Canonical fiscal periods.

Provider adapters convert their own period strings here; nothing
downstream parses provider date formats. Indian fiscal years end 31
March, so FY2026 covers 2025-04-01..2026-03-31.
"""

import re
from datetime import date
from enum import StrEnum

from pydantic import BaseModel

_FY_END_MONTH = 3
_FY_END_DAY = 31

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_FY_PATTERN = re.compile(r"^FY\s*'?(\d{2}|\d{4})$", re.IGNORECASE)
_ISO_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MON_YEAR_PATTERN = re.compile(r"^([A-Za-z]{3,9})\s+(\d{4})$")
_YEAR_PATTERN = re.compile(r"^(\d{4})$")


class PeriodType(StrEnum):
    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"
    UNKNOWN = "UNKNOWN"


class CanonicalPeriod(BaseModel):
    """`FY2026`, `2026-03-31` and `Mar 2026` all normalize to the same value."""

    label: str
    fiscal_year: int | None = None
    period_type: PeriodType = PeriodType.UNKNOWN
    end_date: date | None = None

    def __str__(self) -> str:
        return self.label


def _fiscal_year_for(end: date) -> int:
    """A date on or before 31 March belongs to the fiscal year named for
    that calendar year; after it, the next one."""
    if (end.month, end.day) <= (_FY_END_MONTH, _FY_END_DAY):
        return end.year
    return end.year + 1


def _annual(fiscal_year: int) -> CanonicalPeriod:
    return CanonicalPeriod(
        label=f"FY{fiscal_year}",
        fiscal_year=fiscal_year,
        period_type=PeriodType.ANNUAL,
        end_date=date(fiscal_year, _FY_END_MONTH, _FY_END_DAY),
    )


def normalize_period(raw: str | None) -> CanonicalPeriod:
    """Never raises — an unrecognized period is preserved verbatim and
    marked UNKNOWN rather than being guessed at or dropped."""
    text = (raw or "").strip()
    if not text:
        return CanonicalPeriod(label="UNKNOWN", period_type=PeriodType.UNKNOWN)

    fy = _FY_PATTERN.match(text)
    if fy:
        digits = fy.group(1)
        year = int(digits) if len(digits) == 4 else 2000 + int(digits)
        return _annual(year)

    iso = _ISO_PATTERN.match(text)
    if iso:
        end = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        year = _fiscal_year_for(end)
        # Only a 31-March end date is a full fiscal year; anything else is
        # an interim period and must not be relabelled as annual.
        if (end.month, end.day) == (_FY_END_MONTH, _FY_END_DAY):
            return _annual(year)
        return CanonicalPeriod(
            label=text, fiscal_year=year, period_type=PeriodType.QUARTERLY, end_date=end
        )

    mon = _MON_YEAR_PATTERN.match(text)
    if mon:
        month = _MONTHS.get(mon.group(1)[:3].lower())
        if month is not None:
            year = int(mon.group(2))
            if month == _FY_END_MONTH:
                return _annual(year)
            end = date(year, month, 1)
            return CanonicalPeriod(
                label=text,
                fiscal_year=_fiscal_year_for(end),
                period_type=PeriodType.QUARTERLY,
                end_date=end,
            )

    year_only = _YEAR_PATTERN.match(text)
    if year_only:
        return _annual(int(year_only.group(1)))

    return CanonicalPeriod(label=text, period_type=PeriodType.UNKNOWN)


def same_period(left: str | None, right: str | None) -> bool:
    a, b = normalize_period(left), normalize_period(right)
    if a.period_type == PeriodType.UNKNOWN or b.period_type == PeriodType.UNKNOWN:
        return a.label == b.label
    return a.period_type == b.period_type and a.end_date == b.end_date
