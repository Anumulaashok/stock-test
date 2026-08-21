"""Evidence validation for the report layer.

Mirrors `app.analyst.context.valid_evidence_names` / `app.analyst.parsing`'s
filtering policy, but sourced directly from `CombinedAnalysisResult`
(financial/valuation/scoring/research), since a report may be generated
without ever re-running the analyst's own context builder. An evidence
reference that no longer resolves to anything upstream is dropped, never
invented or left dangling — with a warning recorded either way.
"""

from app.models.analyst import AnalystEvidence
from app.models.financial_results import FinancialAnalysisResult
from app.models.research import ResearchResult
from app.models.scoring import ScoringResult
from app.models.valuation import ValuationRange

_NAMESPACES = ("financial", "valuation", "risk", "research")


def valid_report_evidence_names(
    financial_analysis: FinancialAnalysisResult | None,
    valuation: ValuationRange | None,
    scoring: ScoringResult | None,
    research: ResearchResult | None,
) -> dict[str, set[str]]:
    financial: set[str] = set()
    if financial_analysis:
        financial |= {m.name for m in financial_analysis.metrics}
    if scoring:
        financial |= {c.category for c in scoring.category_scores}

    return {
        "financial": financial,
        "valuation": {r.method for r in valuation.results} if valuation else set(),
        "risk": {r.name for r in scoring.risk_indicators} if scoring else set(),
        "research": (
            {i.id for i in research.items} if research and research.status == "success" else set()
        ),
    }


def filter_evidence(
    evidence: AnalystEvidence, valid_names: dict[str, set[str]]
) -> tuple[AnalystEvidence, list[str]]:
    """Returns `(filtered_evidence, warnings)` — one warning per reference
    that didn't resolve to anything in `valid_names`."""
    warnings: list[str] = []
    filtered: dict[str, list[str]] = {}
    for namespace in _NAMESPACES:
        values = getattr(evidence, namespace)
        valid_set = valid_names.get(namespace, set())
        filtered[namespace] = [v for v in values if v in valid_set]
        for dropped in values:
            if dropped not in valid_set:
                warnings.append(f"removed invalid {namespace} evidence reference: {dropped!r}")
    return AnalystEvidence(**filtered), warnings
