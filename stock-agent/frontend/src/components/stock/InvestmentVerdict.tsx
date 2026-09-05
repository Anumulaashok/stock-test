import type { ReportSummary } from '../../types/backend'
import { toDisplayNumber } from '../../lib/format'
import { useCountUp } from '../../hooks/useCountUp'
import { SignalBadge } from '../SignalBadge'

const BAND_LABEL: Record<string, string> = {
  excellent: 'Excellent',
  strong: 'Attractive',
  good: 'Attractive',
  fair: 'Fair',
  weak: 'Weak',
  poor: 'Unattractive',
}

/** §4: the hero verdict. No confidence percentage is rendered -- the
 * backend does not compute one, and §30/§41 both forbid inventing a
 * number the app can't stand behind. `signal.reason` (already
 * deterministic, see SignalBadge) stands in for a one-line "why". */
export function InvestmentVerdict({ summary }: { summary: ReportSummary }) {
  const score = toDisplayNumber(summary.overall_score, 0)
  const animatedScore = useCountUp(score !== null ? Number(score) : null)
  const bandLabel = summary.score_band ? BAND_LABEL[summary.score_band] : null

  return (
    <section aria-labelledby="verdict-heading" className="surface-card p-6 text-center">
      <h2 id="verdict-heading" className="section-heading justify-center">
        Investment View
      </h2>
      {score !== null ? (
        <div className="mt-3 font-mono-nums text-5xl font-extrabold tracking-tight">{animatedScore}<span className="text-2xl text-[var(--color-text-faint)]">/100</span></div>
      ) : (
        <div className="mt-3 text-lg text-[var(--color-text-faint)]">Score unavailable</div>
      )}
      {bandLabel && (
        <div className="mt-1 text-sm font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">{bandLabel}</div>
      )}
      <div className="mt-4 flex justify-center">
        <SignalBadge signal={summary.signal} />
      </div>
    </section>
  )
}
