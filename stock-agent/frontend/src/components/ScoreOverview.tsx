import type { ReportCategoryScore, ReportScoringSection } from '../types/backend'
import { toDisplayNumber, humanizeKey } from '../lib/format'
import { MetricStatusBadge } from './StatusBadge'

const BAND_COLOR: Record<string, string> = {
  excellent: 'var(--color-status-positive)',
  strong: 'var(--color-status-positive)',
  good: 'var(--color-status-low)',
  fair: 'var(--color-status-medium)',
  weak: 'var(--color-status-high)',
  poor: 'var(--color-status-critical)',
}

function ScoreCard({ category }: { category: ReportCategoryScore }) {
  const score = toDisplayNumber(category.score)
  const color = category.band ? BAND_COLOR[category.band] : 'var(--color-text-faint)'
  return (
    <div
      className="surface-card surface-card--interactive relative overflow-hidden p-3.5"
      style={{ borderLeft: `3px solid ${score !== null ? color : 'var(--color-border)'}` }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-[var(--color-text-muted)]">{humanizeKey(category.category)}</span>
        {category.status !== 'calculated' && <MetricStatusBadge status={category.status} />}
      </div>
      <div className="mt-1.5 font-mono-nums text-[26px] font-bold leading-none" style={{ color: score !== null ? color : undefined }}>
        {score !== null ? score : <span className="text-base font-normal text-[var(--color-text-faint)]">Unavailable</span>}
      </div>
      {category.band && <div className="mt-1 text-xs capitalize text-[var(--color-text-faint)]">{category.band}</div>}
      {category.reason && category.status !== 'calculated' && (
        <p className="mt-1.5 text-xs leading-snug text-[var(--color-text-faint)]">{category.reason}</p>
      )}
    </div>
  )
}

export function ScoreOverview({ scoring }: { scoring: ReportScoringSection | null }) {
  if (!scoring) {
    return (
      <section aria-labelledby="score-overview-heading">
        <h2 id="score-overview-heading" className="section-heading mb-3">
          Score Overview
        </h2>
        <p className="text-sm text-[var(--color-text-faint)]">Scoring is unavailable for this analysis.</p>
      </section>
    )
  }

  return (
    <section aria-labelledby="score-overview-heading">
      <h2 id="score-overview-heading" className="section-heading mb-3">
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
