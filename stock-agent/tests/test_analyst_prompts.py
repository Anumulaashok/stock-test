from decimal import Decimal

from app.analyst.context import build_analyst_context
from app.analyst.prompts import build_context_section, build_system_instructions, build_task_section, build_user_prompt
from app.models.financial_results import FinancialAnalysisResult, FinancialMetricResult
from app.models.financial_results import MetricStatus as FMS
from app.models.scoring import CategoryScore, ScoreStatus, ScoringResult


def d(value) -> Decimal:
    return Decimal(str(value))


def _financial_analysis():
    return FinancialAnalysisResult(
        company="Acme Corp",
        periods_analyzed=["FY2024"],
        metrics=[
            FinancialMetricResult(name="roe", value=d(24), unit="%", status=FMS.CALCULATED),
            FinancialMetricResult(
                name="revenue_growth", value=None, unit="%", status=FMS.UNAVAILABLE,
                reason="previous-period revenue is missing",
            ),
        ],
    )


def _scoring():
    return ScoringResult(
        company_name="Acme Corp",
        overall_score=d(78),
        overall_status=ScoreStatus.CALCULATED,
        category_scores=[
            CategoryScore(category="profitability", score=d(87), weight=d("0.20"), status=ScoreStatus.CALCULATED),
        ],
    )


def test_system_instructions_forbid_recommendations():
    text = build_system_instructions()
    assert "buy, sell, or hold" in text.lower() or "buy" in text.lower()
    assert "recommendation" in text.lower()


def test_system_instructions_forbid_inventing_data():
    text = build_system_instructions()
    assert "never invent" in text.lower()
    assert "never treat" in text.lower() or "unavailable" in text.lower()


def test_system_instructions_require_calculation_authority():
    text = build_system_instructions()
    assert "do not perform independent financial calculations" in text.lower()


def test_context_section_contains_calculated_value():
    context = build_analyst_context(_financial_analysis(), None, _scoring())
    section = build_context_section(context)
    assert '"roe"' in section
    assert "24" in section


def test_context_section_represents_unavailable_explicitly():
    context = build_analyst_context(_financial_analysis(), None, _scoring())
    section = build_context_section(context)
    assert '"revenue_growth"' in section
    assert '"unavailable"' in section
    assert "previous-period revenue is missing" in section


def test_task_section_defines_schema_and_forbids_recommendation_field():
    section = build_task_section()
    assert "investment_thesis" in section
    assert "key_takeaways" in section
    assert '"recommendation"' in section  # named explicitly as forbidden
    assert "only valid json" in section.lower() or "only a single valid json" in section.lower()


def test_user_prompt_combines_context_then_task_in_order():
    context = build_analyst_context(_financial_analysis(), None, _scoring())
    prompt = build_user_prompt(context)
    context_index = prompt.index("Structured Context")
    task_index = prompt.index("Analysis Task")
    assert context_index < task_index


def test_context_section_labels_deterministic_vs_research_evidence():
    context = build_analyst_context(_financial_analysis(), None, _scoring())
    section = build_context_section(context)
    assert "DETERMINISTIC FINANCIAL EVIDENCE" in section
    assert "EXTERNAL RESEARCH CONTEXT" in section


def test_system_instructions_include_research_rules():
    text = build_system_instructions()
    assert "research" in text.lower()
    assert "stale" in text.lower()
    assert "research context was unavailable" in text.lower()


def test_task_section_evidence_schema_has_four_namespaces():
    section = build_task_section()
    for namespace in ("financial", "valuation", "risk", "research"):
        assert f'"{namespace}"' in section
