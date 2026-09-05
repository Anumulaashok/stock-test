import type { ReportMovingAverageCrossover, ReportSignal, ReportTechnicalSignal, SignalColor } from '../types/backend'

/**
 * Single primitive for every deterministic, color-coded "signal" badge
 * in the app (overall strength, technical trend, ...). Each is
 * explicitly NOT a buy/sell/hold recommendation -- see
 * app/reporting/signal.py and app/reporting/technical_signal.py. Color
 * is always paired with text, never used alone.
 */

const COLOR_CLASS: Record<SignalColor, string> = {
  green: 'text-[var(--color-status-positive)] bg-[var(--color-status-positive)]/10 border-[var(--color-status-positive)]/30',
  yellow: 'text-[var(--color-status-medium)] bg-[var(--color-status-medium)]/10 border-[var(--color-status-medium)]/30',
  red: 'text-[var(--color-status-negative)] bg-[var(--color-status-negative)]/10 border-[var(--color-status-negative)]/30',
  gray: 'text-[var(--color-status-info)] bg-[var(--color-status-info)]/10 border-[var(--color-status-info)]/30',
}

interface GenericSignal {
  label: string
  color: SignalColor
  reason: string
}

function SignalBadgeBase({
  signal,
  labelMap,
  align = 'end',
}: {
  signal: GenericSignal | null
  labelMap: Record<string, string>
  align?: 'start' | 'end'
}) {
  if (!signal) return null

  return (
    <div className={`flex flex-col gap-1.5 ${align === 'end' ? 'items-end' : 'items-start'}`}>
      <span
        title={signal.reason}
        className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold shadow-[var(--shadow-xs)] ${COLOR_CLASS[signal.color]}`}
      >
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
        {labelMap[signal.label] ?? signal.label}
      </span>
      <p className={`max-w-[16rem] text-[11px] leading-snug text-[var(--color-text-faint)] ${align === 'end' ? 'text-right' : 'text-left'}`}>
        {signal.reason}
      </p>
    </div>
  )
}

const STRENGTH_LABEL: Record<ReportSignal['label'], string> = {
  strong: 'Strong',
  moderate: 'Moderate',
  weak: 'Weak',
  unavailable: 'Unavailable',
}

export function SignalBadge({ signal }: { signal: ReportSignal | null }) {
  return <SignalBadgeBase signal={signal} labelMap={STRENGTH_LABEL} align="end" />
}

const TECHNICAL_SIGNAL_LABEL: Record<ReportTechnicalSignal['label'], string> = {
  bullish: 'Bullish',
  bearish: 'Bearish',
  neutral: 'Neutral',
  mixed: 'Mixed signals',
  unavailable: 'Unavailable',
}

export function TechnicalSignalBadge({ signal }: { signal: ReportTechnicalSignal | null }) {
  return <SignalBadgeBase signal={signal} labelMap={TECHNICAL_SIGNAL_LABEL} align="start" />
}

const CROSSOVER_COLOR: Record<string, SignalColor> = {
  golden_cross: 'green',
  death_cross: 'red',
  neutral: 'gray',
}

const CROSSOVER_LABEL: Record<string, string> = {
  golden_cross: 'Golden Cross',
  death_cross: 'Death Cross',
  neutral: 'Neutral',
  unavailable: 'Unavailable',
}

/** Reads `crossover.signal` directly -- never recomputed from the two
 * moving-average values client-side (I2). `golden_cross`/`death_cross`
 * are the backend's own vocabulary (app/forecasting/calculations.py),
 * not a buy/sell call. */
export function CrossoverBadge({ crossover }: { crossover: ReportMovingAverageCrossover | null }) {
  if (!crossover || !crossover.signal) return null
  const generic = {
    label: crossover.signal,
    color: CROSSOVER_COLOR[crossover.signal] ?? 'gray',
    reason: crossover.reason ?? `${crossover.short_window}/${crossover.long_window}-day moving average crossover.`,
  }
  return <SignalBadgeBase signal={generic} labelMap={CROSSOVER_LABEL} align="start" />
}
