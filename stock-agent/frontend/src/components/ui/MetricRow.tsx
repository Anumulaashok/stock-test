import type { ReactNode } from 'react'

/** One metric line -- label, value, optional status/badge slot. Missing
 * data is always rendered as "Unavailable" plus the backend's real
 * reason, passed in by the caller -- never a bare `N/A`/`0`/`NaN` (§20). */
export function MetricRow({
  label,
  value,
  reason,
  badge,
}: {
  label: string
  value: string | null
  reason?: string | null
  badge?: ReactNode
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="text-sm text-[var(--color-text-muted)]">{label}</span>
      <div className="flex items-center gap-2">
        {value !== null ? (
          <span className="font-mono-nums text-sm font-semibold">{value}</span>
        ) : (
          <span className="text-right text-xs text-[var(--color-text-faint)]" title={reason ?? undefined}>
            Unavailable{reason ? ` — ${reason}` : ''}
          </span>
        )}
        {badge}
      </div>
    </div>
  )
}
