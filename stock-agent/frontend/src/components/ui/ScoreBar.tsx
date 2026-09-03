import type { ReactNode } from 'react'
import type { ScoreBand } from '../../types/backend'

const BAND_COLOR: Record<ScoreBand, string> = {
  excellent: 'var(--color-status-positive)',
  strong: 'var(--color-status-positive)',
  good: 'var(--color-status-low)',
  fair: 'var(--color-status-medium)',
  weak: 'var(--color-status-high)',
  poor: 'var(--color-status-critical)',
}

/** A horizontal score row -- label, bar, numeric value, qualitative
 * band -- used for every score/sub-score breakdown in the app instead
 * of a grid of colored cards, so comparing several scores at once is a
 * straight visual read down a column rather than a hunt across a grid. */
export function ScoreBar({
  label,
  score,
  band,
  unavailableReason,
  action,
}: {
  label: string
  score: number | null
  band?: ScoreBand | null
  unavailableReason?: string | null
  action?: ReactNode
}) {
  const color = band ? BAND_COLOR[band] : 'var(--color-text-faint)'
  const pct = score !== null ? Math.max(0, Math.min(100, score)) : 0

  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="w-36 shrink-0 truncate text-sm text-[var(--color-text-muted)]">{label}</span>
      <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--color-border)]">
        {score !== null && (
          <div className="h-full rounded-full transition-[width]" style={{ width: `${pct}%`, background: color }} />
        )}
      </div>
      <span className="w-12 shrink-0 text-right font-mono-nums text-sm font-semibold" style={score !== null ? { color } : undefined}>
        {score !== null ? score : '—'}
      </span>
      {band ? (
        <span className="w-16 shrink-0 truncate text-xs capitalize text-[var(--color-text-faint)]">{band}</span>
      ) : (
        <span className="w-16 shrink-0 truncate text-xs text-[var(--color-text-faint)]" title={unavailableReason ?? undefined}>
          {unavailableReason ? 'No data' : ''}
        </span>
      )}
      {action}
    </div>
  )
}
