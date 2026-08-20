from app.financial.periods import period_sort_key, sort_periods


def test_sort_periods_annual():
    assert sort_periods(["FY2025", "FY2023", "FY2024"]) == ["FY2023", "FY2024", "FY2025"]


def test_sort_periods_quarterly_within_year():
    assert sort_periods(["2024-Q4", "2024-Q1", "2024-Q3", "2024-Q2"]) == [
        "2024-Q1",
        "2024-Q2",
        "2024-Q3",
        "2024-Q4",
    ]


def test_sort_periods_mixed_years_and_quarters():
    periods = ["2023-Q4", "2024-Q1", "2022-Q2", "2024-Q4"]
    assert sort_periods(periods) == ["2022-Q2", "2023-Q4", "2024-Q1", "2024-Q4"]


def test_period_sort_key_unrecognized_format_is_stable():
    # No parseable year — falls back to string comparison rather than crashing.
    key_a = period_sort_key("period-a")
    key_b = period_sort_key("period-b")
    assert key_a < key_b
