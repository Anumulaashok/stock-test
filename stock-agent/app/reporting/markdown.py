"""Pure Markdown rendering of an `InvestmentResearchReport`.

Presentation only — no calculation, no recommendation. Every value shown
here already exists on the report; this module only formats it as text.
"""

from app.models.report import InvestmentResearchReport


def _bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "_None._"


def _metrics_table(metrics) -> str:
    if not metrics:
        return "_No data available._"
    lines = ["| Metric | Value | Status |", "|---|---:|---|"]
    for metric in metrics:
        value = metric.formatted_value if metric.formatted_value is not None else "unavailable"
        lines.append(f"| {metric.name} | {value} | {metric.status} |")
    return "\n".join(lines)


def render_markdown(report: InvestmentResearchReport) -> str:
    lines: list[str] = []
    header = report.company.name
    if report.company.ticker:
        header += f" ({report.company.ticker})"
    lines.append(f"# {header}")
    lines.append(f"\n_Report status: {report.status.value}_")

    lines.append("\n## Executive Summary\n")
    score = f"{report.summary.overall_score}" if report.summary.overall_score is not None else "unavailable"
    lines.append(f"Overall Score: {score} / 100  ")
    lines.append(f"Band: {report.summary.score_band or 'unavailable'}\n")
    if report.summary.investment_thesis:
        lines.append(report.summary.investment_thesis + "\n")
    if report.summary.key_takeaways:
        lines.append("**Key takeaways:**\n")
        lines.append(_bullet_list(report.summary.key_takeaways))

    if report.financials:
        lines.append("\n## Financial Analysis\n")
        for label, metrics in (
            ("Profitability", report.financials.profitability),
            ("Growth", report.financials.growth),
            ("Financial Health", report.financials.financial_health),
            ("Cash Flow", report.financials.cash_flow),
        ):
            lines.append(f"\n### {label}\n")
            lines.append(_metrics_table(metrics))

    if report.valuation:
        lines.append("\n## Valuation\n")
        price = report.valuation.formatted_current_share_price or "unavailable"
        lines.append(f"Current price: {price}\n")
        lines.append("| Method | Value/Share | Upside/Downside | Status |")
        lines.append("|---|---:|---:|---|")
        for method in report.valuation.methods:
            value = method.formatted_value_per_share or "unavailable"
            upside = method.formatted_upside_downside or "unavailable"
            lines.append(f"| {method.method} | {value} | {upside} | {method.status} |")

    if report.scoring:
        lines.append("\n## Scoring\n")
        lines.append("| Category | Score | Band | Status |")
        lines.append("|---|---:|---|---|")
        for category in report.scoring.categories:
            score_display = f"{category.score}" if category.score is not None else "unavailable"
            lines.append(
                f"| {category.category} | {score_display} | {category.band or '-'} | {category.status} |"
            )

    if report.risk:
        lines.append("\n## Risk\n")
        for label, indicators in (
            ("Critical", report.risk.critical), ("High", report.risk.high),
            ("Medium", report.risk.medium), ("Low", report.risk.low),
        ):
            if not indicators:
                continue
            lines.append(f"\n### {label}\n")
            for indicator in indicators:
                lines.append(f"- **{indicator.name}**: {indicator.reason}")

    if report.research and report.research.available:
        lines.append("\n## Research Context\n")
        for item in report.research.items:
            lines.append(f"\n**{item.id}** — {item.title}")
            lines.append(f"Publisher: {item.publisher or 'unknown'}  ")
            lines.append(f"Published: {item.published_at or 'unknown'}  ")
            lines.append(f"Freshness: {item.freshness}  ")
            lines.append(f"URL: {item.url}")
    elif report.research is not None:
        lines.append("\n## Research Context\n\n_No research context available._")

    if report.analyst and report.analyst.available:
        lines.append("\n## AI Analyst\n")
        lines.append("**Strengths:**\n")
        lines.append(_bullet_list(report.analyst.strengths))
        lines.append("\n**Weaknesses:**\n")
        lines.append(_bullet_list(report.analyst.weaknesses))
        for category in report.analyst.category_analysis:
            lines.append(f"\n### {category.category.replace('_', ' ').title()}\n")
            lines.append(category.text)
        lines.append("\n**Caveats:**\n")
        lines.append(_bullet_list(report.analyst.caveats))

    if report.warnings:
        lines.append("\n## Warnings / Limitations\n")
        for warning in report.warnings:
            lines.append(f"- [{warning.source}] {warning.message}")

    lines.append(
        f"\n---\n_Generated {report.metadata.generated_at} · report v{report.metadata.report_version}._"
    )
    return "\n".join(lines)
