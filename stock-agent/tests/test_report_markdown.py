from datetime import datetime, timezone

from app.reporting.markdown import render_markdown
from app.reporting.service import ReportService
from tests.test_report_service import _combined


def _report():
    return ReportService(clock=lambda: datetime(2026, 3, 1, tzinfo=timezone.utc)).generate(_combined())


def test_markdown_includes_company_header():
    md = render_markdown(_report())
    assert "# Acme Corp (ACME)" in md


def test_markdown_includes_score():
    md = render_markdown(_report())
    assert "78" in md
    assert "Band: good" in md


def test_markdown_includes_financial_section():
    md = render_markdown(_report())
    assert "## Financial Analysis" in md
    assert "roe" in md


def test_markdown_includes_valuation_table():
    md = render_markdown(_report())
    assert "## Valuation" in md
    assert "| dcf |" in md
    assert "$140.00" in md


def test_markdown_includes_research_sources():
    md = render_markdown(_report())
    assert "## Research Context" in md
    assert "research_001" in md
    assert "Example News" in md


def test_markdown_includes_analyst_sections():
    md = render_markdown(_report())
    assert "## AI Analyst" in md
    assert "Strong ROE" in md


def test_markdown_includes_warnings():
    md = render_markdown(_report())
    assert "## Warnings / Limitations" in md


def test_markdown_never_contains_recommendation_language():
    md = render_markdown(_report())
    lowered = md.lower()
    assert "buy" not in lowered
    assert "sell" not in lowered
    assert " hold " not in lowered
    assert "recommend" not in lowered
