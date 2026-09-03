import type { InvestmentResearchReport } from '../../types/backend'

/** §7. Prefers the real LLM-generated `investment_thesis`, labelled as
 * generated interpretation. When the analyst didn't run
 * (`analyst.available === false` / `null`), falls back to a short
 * deterministic sentence built only from already-computed score/band
 * fields -- never a fabricated narrative claiming to be AI-written. */
export function InvestorSummary({ report }: { report: InvestmentResearchReport }) {
  const thesis = report.analyst?.available ? report.analyst.investment_thesis : null

  if (thesis) {
    return (
      <section aria-labelledby="investor-summary-heading" className="surface-card p-5">
        <h2 id="investor-summary-heading" className="section-heading mb-2">
          Investor Summary
        </h2>
        <p className="text-sm leading-relaxed text-[var(--color-text-muted)]">{thesis}</p>
        <p className="mt-2 text-xs text-[var(--color-text-faint)]">AI-generated interpretation of the data below — not a recommendation.</p>
      </section>
    )
  }

  const band = report.summary.score_band
  const topCategory = (report.scoring?.categories ?? [])
    .filter((c) => c.band === 'excellent' || c.band === 'strong')
    .sort((a, b) => Number(b.score ?? 0) - Number(a.score ?? 0))[0]
  const weakCategory = (report.scoring?.categories ?? [])
    .filter((c) => c.band === 'weak' || c.band === 'poor')
    .sort((a, b) => Number(a.score ?? 0) - Number(b.score ?? 0))[0]

  if (!band && !topCategory && !weakCategory) return null

  const sentences: string[] = []
  if (band) sentences.push(`This analysis rates the overall picture as ${band}.`)
  if (topCategory) sentences.push(`${topCategory.category.replace(/_/g, ' ')} is the strongest contributor.`)
  if (weakCategory) sentences.push(`${weakCategory.category.replace(/_/g, ' ')} is the main area to watch.`)

  return (
    <section aria-labelledby="investor-summary-heading" className="surface-card p-5">
      <h2 id="investor-summary-heading" className="section-heading mb-2">
        Investor Summary
      </h2>
      <p className="text-sm leading-relaxed text-[var(--color-text-muted)]">{sentences.join(' ')}</p>
      <p className="mt-2 text-xs text-[var(--color-text-faint)]">
        Deterministic summary built from the computed scores below — the AI analyst did not run for this analysis.
      </p>
    </section>
  )
}
