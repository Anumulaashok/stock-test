"""`compute_input_hash` must be stable across otherwise-identical inputs
that differ only in a fetch timestamp -- if it isn't, LLM-call reuse
(the single most expensive thing this feature exists to prevent) never
fires, because every research run would produce a different hash."""

from decimal import Decimal

from app.financial.service import FinancialAnalysisService
from app.models.financial_statements import CompanyFinancials, IncomeStatement
from app.models.research import ResearchFreshness, ResearchItem, ResearchResult, ResearchSource, SourceType
from app.models.scoring import CategoryScore, ScoreStatus, ScoringResult
from app.snapshot.hashing import compute_input_hash


def d(value) -> Decimal:
    return Decimal(str(value))


def _financial_analysis_dict() -> dict:
    financials = CompanyFinancials(
        company_name="Acme Corp",
        income_statements=[IncomeStatement(period="FY2025", revenue=d(100), net_income=d(10))],
    )
    result = FinancialAnalysisService().analyze(financials)
    return result.model_dump(mode="json")


def _scoring_dict() -> dict:
    return ScoringResult(
        company_name="Acme Corp", overall_score=d(70), overall_status=ScoreStatus.CALCULATED,
        category_scores=[CategoryScore(category="profitability", score=d(70), weight=d("1.0"), status=ScoreStatus.CALCULATED)],
    ).model_dump(mode="json")


def _research_result(retrieved_at: str) -> dict:
    return ResearchResult(
        status="success",
        items=[
            ResearchItem(
                id="item-1", title="Acme expands",
                source=ResearchSource(
                    title="Acme expands", publisher="Example News",
                    url="https://example.com/a", source_type=SourceType.NEWS,
                ),
                published_at="2026-08-01T00:00:00Z", freshness=ResearchFreshness.RECENT, relevance=d("0.9"),
                summary="Expansion summary.",
            )
        ],
        retrieved_at=retrieved_at,
    ).model_dump(mode="json")


def test_hash_is_stable_when_only_retrieved_at_changes():
    financial_analysis = _financial_analysis_dict()
    scoring = _scoring_dict()

    hash_a = compute_input_hash(
        financial_analysis=financial_analysis, valuation=None, scoring=scoring,
        research=_research_result("2026-09-02T10:00:00Z"),
        prompt_version="v1", model="test-model",
    )
    hash_b = compute_input_hash(
        financial_analysis=financial_analysis, valuation=None, scoring=scoring,
        research=_research_result("2026-09-02T18:45:12Z"),  # same content, fetched hours later
        prompt_version="v1", model="test-model",
    )

    assert hash_a == hash_b


def test_hash_changes_when_actual_content_changes():
    financial_analysis = _financial_analysis_dict()
    scoring = _scoring_dict()

    base_hash = compute_input_hash(
        financial_analysis=financial_analysis, valuation=None, scoring=scoring, research=None,
        prompt_version="v1", model="test-model",
    )
    different_scoring = _scoring_dict()
    different_scoring["overall_score"] = "50"

    changed_hash = compute_input_hash(
        financial_analysis=financial_analysis, valuation=None, scoring=different_scoring, research=None,
        prompt_version="v1", model="test-model",
    )

    assert base_hash != changed_hash


def test_hash_changes_with_prompt_version_or_model():
    financial_analysis = _financial_analysis_dict()
    scoring = _scoring_dict()

    base = compute_input_hash(
        financial_analysis=financial_analysis, valuation=None, scoring=scoring, research=None,
        prompt_version="v1", model="model-a",
    )
    other_prompt = compute_input_hash(
        financial_analysis=financial_analysis, valuation=None, scoring=scoring, research=None,
        prompt_version="v2", model="model-a",
    )
    other_model = compute_input_hash(
        financial_analysis=financial_analysis, valuation=None, scoring=scoring, research=None,
        prompt_version="v1", model="model-b",
    )

    assert base != other_prompt
    assert base != other_model


def test_hash_is_deterministic_for_identical_calls():
    financial_analysis = _financial_analysis_dict()
    scoring = _scoring_dict()

    first = compute_input_hash(
        financial_analysis=financial_analysis, valuation=None, scoring=scoring, research=None,
        prompt_version="v1", model="test-model",
    )
    second = compute_input_hash(
        financial_analysis=financial_analysis, valuation=None, scoring=scoring, research=None,
        prompt_version="v1", model="test-model",
    )

    assert first == second
