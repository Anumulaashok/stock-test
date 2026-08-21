"""Aggregates warnings from every upstream result into `ReportWarning`s,
each tagged with its source. Deduplicated by message text so a warning
already captured from a specific source (e.g. "research") isn't repeated
under the generic "pipeline" bucket when it also appears in
`CombinedAnalysisResult.warnings`.
"""

from app.models.report import ReportWarning
from app.pipeline.models import CombinedAnalysisResult


def collect_warnings(combined: CombinedAnalysisResult) -> list[ReportWarning]:
    warnings: list[ReportWarning] = []
    seen_messages: set[str] = set()

    def add(source: str, message: str, code: str | None = None) -> None:
        if message in seen_messages:
            return
        seen_messages.add(message)
        warnings.append(ReportWarning(source=source, code=code, message=message))

    if combined.financial_analysis:
        for message in combined.financial_analysis.warnings:
            add("financial_analysis", message)
    if combined.valuation:
        for message in combined.valuation.warnings:
            add("valuation", message)
    if combined.scoring:
        for message in combined.scoring.warnings:
            add("scoring", message)
    if combined.research:
        for message in combined.research.warnings:
            add("research", message)
        if combined.research.status != "success" and combined.research.error:
            add("research", combined.research.error.message, code=combined.research.error.code.value)
    if combined.analyst and combined.analyst.status != "success" and combined.analyst.error:
        add("analyst", combined.analyst.error.message, code=combined.analyst.error.code.value)

    # Anything the pipeline synthesized that isn't already captured above
    # (e.g. "no research service configured", a failed-stage message).
    for message in combined.warnings:
        add("pipeline", message)

    return warnings
