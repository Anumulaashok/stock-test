"""Fiscal period sorting.

Financial statement lists may arrive in any order. Periods are plain
labels (e.g. "FY2024", "2024-Q4", "2023"), so ordering them correctly
means extracting a comparable (year, quarter) key rather than assuming
chronological input order or relying on plain string sort, which breaks
across formats and year boundaries beyond single digits.
"""

import re

_YEAR_RE = re.compile(r"(19|20)\d{2}")
_QUARTER_RE = re.compile(r"Q([1-4])", re.IGNORECASE)


def period_sort_key(period: str) -> tuple[int, int, str]:
    """Build a sort key that orders periods chronologically.

    Extracts a four-digit year (0 if none found) and a quarter number
    1-4 (0 if not a quarterly period, sorting a full-year period before
    Q1-Q4 of the same year). The original string is a final tiebreaker
    so the ordering is always well-defined and stable.
    """
    year_match = _YEAR_RE.search(period)
    year = int(year_match.group()) if year_match else 0
    quarter_match = _QUARTER_RE.search(period)
    quarter = int(quarter_match.group(1)) if quarter_match else 0
    return (year, quarter, period)


def sort_periods(periods: list[str]) -> list[str]:
    """Return `periods` sorted chronologically (ascending)."""
    return sorted(periods, key=period_sort_key)
