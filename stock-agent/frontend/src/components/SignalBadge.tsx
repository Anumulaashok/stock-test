import type { ReportSignal } from '../types/backend'

/**
 * Renders the deterministic strength/risk signal (green/yellow/red/gray)
 * derived from the score band and risk indicators. This is explicitly
 * NOT a buy/sell/hold recommendation -- see app/reporting/signal.py.
 * Color is always paired with text, never used alone.
 */

const LABEL: Record<ReportSignal['label'], string> = {
  strong: 'Strong',
  moderate: 'Moderate',
  weak: 'Weak',
  unavailable: 'Unavailable',
}

const COLOR_CLASS: Record<ReportSignal['color'], string> = {
  green: 'text-[var(--color-status-positive)] bg-[var(--color-status-positive)]/10 border-[var(--color-status-positive)]/30',
  yellow: 'text-[var(--color-status-medium)] bg-[var(--color-status-medium)]/10 border-[var(--color-status-medium)]/30',
  red: 'text-[var(--color-status-negative)] bg-[var(--color-status-negative)]/10 border-[var(--color-status-negative)]/30',
  gray: 'text-[var(--color-status-info)] bg-[var(--color-status-info)]/10 border-[var(--color-status-info)]/30',
}

export function SignalBadge({ signal }: { signal: ReportSignal | null }) {
  if (!signal) return null

  return (
    <div className="flex flex-col items-end gap-1">
      <span
        title={signal.reason}
        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${COLOR_CLASS[signal.color]}`}
      >
        <span aria-hidden className="h-2 w-2 rounded-full bg-current" />
        {LABEL[signal.label]}
      </span>
      <p className="max-w-[16rem] text-right text-[11px] leading-snug text-[var(--color-text-faint)]">
        {signal.reason}
      </p>
    </div>
  )
}
