import type { ReportScoringSection } from '../../types/backend'
import { toDisplayNumber, humanizeKey } from '../../lib/format'
import { ScoreBar } from '../ui/ScoreBar'
import { Disclosure } from '../ui/Disclosure'
import { EmptyState } from '../SectionHeader'

/** §5: the score components as comparable horizontal rows instead of a
 * grid of large colored cards -- easier to scan down, and each row
 * expands to the real sub-components the backend computed (never
 * fabricated sub-metrics). */
export function ScoreBreakdown({ scoring }: { scoring: ReportScoringSection | null }) {
  if (!scoring || scoring.categories.length === 0) {
    return <EmptyState title="Score breakdown unavailable" reason="Scoring did not run for this analysis." />
  }

  return (
    <section aria-labelledby="score-breakdown-heading">
      <h2 id="score-breakdown-heading" className="section-heading mb-2">
        Score Breakdown
      </h2>
      <div className="surface-card divide-y divide-[var(--color-border)] px-4">
        {scoring.categories.map((category) => {
          const score = toDisplayNumber(category.score, 0)
          const scoreNum = score !== null ? Number(score) : null
          return (
            <div key={category.category} className="py-1">
              <ScoreBar label={humanizeKey(category.category)} score={scoreNum} band={category.band} unavailableReason={category.reason} />
              {category.components.length > 0 && (
                <Disclosure summary={<span className="text-xs text-[var(--color-text-faint)]">What makes up this score</span>}>
                  <div className="flex flex-col gap-1 pb-2">
                    {category.components.map((component) => {
                      const componentScore = toDisplayNumber(component.score, 0)
                      return (
                        <div key={component.name} className="flex items-center justify-between gap-2 text-xs">
                          <span className="text-[var(--color-text-faint)]">{humanizeKey(component.name)}</span>
                          <span className="font-mono-nums">
                            {componentScore !== null ? componentScore : component.reason ?? 'Unavailable'}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </Disclosure>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
