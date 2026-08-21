import type { ReportCategoryScore, ReportScoringSection } from '../types/backend'
import { toDisplayNumber, humanizeKey } from '../lib/format'
import { MetricStatusBadge } from './StatusBadge'

function ScoreCard({ category }: { category: ReportCategoryScore }) {
  const score = toDisplayNumber(category.score)
  return (
    <div className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-[var(--color-text-muted)]">{humanizeKey(category.category)}</span>
        {category.status !== 'calculated' && <MetricStatusBadge status={category.status} />}
      </div>
      <div className="mt-1 font-mono-nums text-2xl font-semibold">
        {score !== null ? score : <span className="text-base font-normal text-[var(--color-text-faint)]">Unavailable</span>}
      </div>
      {category.band && <div className="text-xs capitalize text-[var(--color-text-muted)]">{category.band}</div>}
      {category.reason && category.status !== 'calculated' && (
        <p className="mt-1 text-xs text-[var(--color-text-faint)]">{category.reason}</p>
      )}
    </div>
  )
}

export function ScoreOverview({ scoring }: { scoring: ReportScoringSection | null }) {
  if (!scoring) {
    return (
      <section aria-labelledby="score-overview-heading">
        <h2 id="score-overview-heading" className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          Score Overview
        </h2>
        <p className="text-sm text-[var(--color-text-faint)]">Scoring is unavailable for this analysis.</p>
      </section>
    )
  }

  return (
    <section aria-labelledby="score-overview-heading">
      <h2 id="score-overview-heading" className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
        Score Overview
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {scoring.categories.map((category) => (
          <ScoreCard key={category.category} category={category} />
        ))}
      </div>
    </section>
  )
}
