import { toDisplayNumber } from '../../lib/format'
import type { InvestmentResearchReport, ScoreBand } from '../../types/backend'

const BAND_LABEL: Record<ScoreBand, string> = {
  excellent: 'Excellent',
  strong: 'Attractive',
  good: 'Attractive',
  fair: 'Fair',
  weak: 'Weak',
  poor: 'Unattractive',
}

const BAND_COLOR: Record<ScoreBand, string> = {
  excellent: 'var(--color-status-positive)',
  strong: 'var(--color-status-positive)',
  good: 'var(--color-status-positive)',
  fair: 'var(--color-status-medium)',
  weak: 'var(--color-status-negative)',
  poor: 'var(--color-status-negative)',
}

/** The single top positive and top watch item, reusing the same
 * analyst-first-then-category-reason fallback `WhyThisScore` uses (not
 * shared as a common function -- `WhyThisScore` is pre-existing code
 * from before this session, not rewritten here without being asked;
 * see DECISIONS.md). Sliced to one each for a fast-glance card; the
 * full lists stay in `WhyThisScore` further down the tab. Exported for
 * unit testing. */
export function topPositiveAndWatch(report: InvestmentResearchReport): { positive: string | null; watch: string | null } {
  const analystRan = report.analyst?.available
  const positives = analystRan ? report.analyst!.strengths : []
  const watch = analystRan ? report.analyst!.weaknesses : []

  const categories = report.scoring?.categories ?? []
  const fallbackPositives = !analystRan
    ? categories.filter((c) => c.band === 'excellent' || c.band === 'strong' || c.band === 'good').map((c) => c.reason).filter((r): r is string => Boolean(r))
    : []
  const fallbackWatch = !analystRan
    ? categories.filter((c) => c.band === 'weak' || c.band === 'poor' || c.band === 'fair').map((c) => c.reason).filter((r): r is string => Boolean(r))
    : []

  const positiveItems = positives.length > 0 ? positives : fallbackPositives
  const watchItems = watch.length > 0 ? watch : fallbackWatch

  return { positive: positiveItems[0] ?? null, watch: watchItems[0] ?? null }
}

/** How many of the report's scoring categories actually produced a
 * number -- reshapes `scoring.categories[].status`, computes nothing
 * the backend didn't already determine per category. Exported for unit
 * testing. */
export function scoreCoverage(report: InvestmentResearchReport): { scored: number; total: number } | null {
  const categories = report.scoring?.categories
  if (!categories || categories.length === 0) return null
  return { scored: categories.filter((c) => c.status === 'calculated').length, total: categories.length }
}

/**
 * Dense, terminal-style summary strip atop the Overview tab -- score,
 * band, top positive/watch item, data provenance (provider +
 * freshness), and how many scoring inputs actually resolved. Distinct
 * in tone from `InvestmentVerdict`'s centered hero card below it: this
 * is a fast-glance dashboard row, not the verdict itself.
 *
 * No regime badge here -- `regime` only reaches the frontend via the ML
 * forecast fetch (`MlForecastResult`, Forecast tab), not `report`
 * itself; adding it here would mean a new fetch on a tab that doesn't
 * otherwise need one. Deferred alongside the other regime-band work per
 * explicit instruction (see DECISIONS.md).
 */
export function SignalCard({ report }: { report: InvestmentResearchReport }) {
  const score = toDisplayNumber(report.summary.overall_score, 0)
  const scoreNumber = report.summary.overall_score === null ? null : Number(report.summary.overall_score)
  const band = report.summary.score_band
  const bandColor = band ? BAND_COLOR[band] : 'var(--color-text-faint)'
  const { positive, watch } = topPositiveAndWatch(report)
  const coverage = scoreCoverage(report)
  const market = report.market

  return (
    <section aria-label="Signal summary" className="surface-card flex flex-col gap-3 p-4 font-mono-nums">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-extrabold" style={{ color: bandColor }}>
            {score ?? '—'}
          </span>
          <span className="text-sm text-[var(--color-text-faint)]">/100</span>
        </div>
        <div className="h-2 min-w-[6rem] flex-1 overflow-hidden rounded-full bg-[var(--color-surface)]">
          <div
            className="h-full rounded-full"
            style={{
              width: scoreNumber !== null && !Number.isNaN(scoreNumber) ? `${Math.max(0, Math.min(100, scoreNumber))}%` : '0%',
              background: bandColor,
            }}
          />
        </div>
        {band && (
          <span
            className="rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide"
            style={{ color: bandColor, borderColor: bandColor }}
          >
            {BAND_LABEL[band]}
          </span>
        )}
        {coverage && (
          <span className="text-xs text-[var(--color-text-faint)]" title="Scoring categories that produced a number">
            {coverage.scored}/{coverage.total} inputs
          </span>
        )}
      </div>

      {(positive || watch) && (
        <div className="flex flex-col gap-1 text-xs sm:flex-row sm:gap-4">
          {positive && (
            <span className="text-[var(--color-status-positive)]">
              <span aria-hidden>+</span> {positive}
            </span>
          )}
          {watch && (
            <span className="text-[var(--color-status-medium)]">
              <span aria-hidden>−</span> {watch}
            </span>
          )}
        </div>
      )}

      {market && (
        <div className="text-[0.6875rem] text-[var(--color-text-faint)]">
          {market.source} · {market.freshness}
          {market.market_timestamp ? ` · ${market.market_timestamp}` : ''}
        </div>
      )}
    </section>
  )
}
