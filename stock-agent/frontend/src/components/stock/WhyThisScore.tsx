import type { InvestmentResearchReport } from '../../types/backend'

/** §6: positive/watch contributors. Prefers the LLM analyst's
 * strengths/weaknesses when it ran; falls back to the deterministic
 * category `reason` strings (already computed by scoring) when it
 * didn't -- never fabricates either list. Returns null rather than an
 * empty card when neither source has anything to show. */
export function WhyThisScore({ report }: { report: InvestmentResearchReport }) {
  const analystRan = report.analyst?.available
  const positives = analystRan ? report.analyst!.strengths : []
  const watch = analystRan ? report.analyst!.weaknesses : []

  const fallbackPositives = !analystRan
    ? (report.scoring?.categories ?? [])
        .filter((c) => c.band === 'excellent' || c.band === 'strong' || c.band === 'good')
        .map((c) => c.reason)
        .filter((r): r is string => Boolean(r))
    : []
  const fallbackWatch = !analystRan
    ? (report.scoring?.categories ?? [])
        .filter((c) => c.band === 'weak' || c.band === 'poor' || c.band === 'fair')
        .map((c) => c.reason)
        .filter((r): r is string => Boolean(r))
    : []

  const positiveItems = positives.length > 0 ? positives : fallbackPositives
  const watchItems = watch.length > 0 ? watch : fallbackWatch

  if (positiveItems.length === 0 && watchItems.length === 0) return null

  return (
    <section aria-labelledby="why-score-heading">
      <h2 id="why-score-heading" className="section-heading mb-2">
        Why This Score?
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {positiveItems.length > 0 && (
          <div className="surface-card p-4">
            <p className="metric-label mb-2 text-[var(--color-status-positive)]">Positive</p>
            <ul className="flex flex-col gap-1.5 text-sm">
              {positiveItems.map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span aria-hidden className="text-[var(--color-status-positive)]">✓</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}
        {watchItems.length > 0 && (
          <div className="surface-card p-4">
            <p className="metric-label mb-2 text-[var(--color-status-medium)]">Watch</p>
            <ul className="flex flex-col gap-1.5 text-sm">
              {watchItems.map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span aria-hidden className="text-[var(--color-status-medium)]">⚠</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  )
}
