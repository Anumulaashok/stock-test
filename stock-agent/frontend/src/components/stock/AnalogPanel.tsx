import { EmptyState } from '../SectionHeader'
import type { AnalogSummary, QuantileEstimate } from '../../types/mlForecast'

function pct(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(decimals)}%`
}

function pctSigned(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(decimals)}%`
}

function StatWithN({ label, value, sampleSize }: { label: string; value: string; sampleSize: number }) {
  return (
    <div>
      <div className="support-text text-xs">{label}</div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-sm font-semibold">{value}</span>
        <span className="support-text text-xs">n={sampleSize}</span>
      </div>
    </div>
  )
}

const QUANTILE_STOPS: { key: keyof QuantileEstimate; label: string }[] = [
  { key: 'p10', label: 'P10' },
  { key: 'p25', label: 'P25' },
  { key: 'p50', label: 'P50' },
  { key: 'p75', label: 'P75' },
  { key: 'p90', label: 'P90' },
]

/** A distribution strip beats a point estimate -- positions each
 * quantile mark along its own real value rather than evenly spaced, so
 * skew in the underlying analog returns is visible, not flattened away.
 * Falls back to a plain list if the bounding quantiles are missing,
 * since positioning against an unknown range would fabricate geometry. */
function QuantileStrip({ quantiles }: { quantiles: QuantileEstimate }) {
  if (quantiles.p10 === null || quantiles.p90 === null) {
    const available = QUANTILE_STOPS.filter((s) => quantiles[s.key] !== null)
    if (available.length === 0) return null
    return (
      <div className="flex flex-wrap gap-3 text-xs">
        {available.map((s) => (
          <span key={s.key}>
            {s.label}: {pctSigned(quantiles[s.key])}
          </span>
        ))}
      </div>
    )
  }

  const min = quantiles.p10
  const max = quantiles.p90
  const span = max - min || 1
  return (
    <div className="pt-2">
      <div className="relative h-1 rounded-full bg-[var(--color-border)]">
        {QUANTILE_STOPS.map((s) => {
          const v = quantiles[s.key]
          if (v === null) return null
          const leftPct = Math.min(100, Math.max(0, ((v - min) / span) * 100))
          return (
            <div
              key={s.key}
              className="absolute top-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center"
              style={{ left: `${leftPct}%` }}
            >
              <span
                aria-hidden
                className={`block h-2.5 w-2.5 rounded-full border-2 border-[var(--color-bg)] ${s.key === 'p50' ? 'bg-[var(--color-accent-strong)]' : 'bg-[var(--color-text-faint)]'}`}
              />
            </div>
          )
        })}
      </div>
      <div className="mt-3 flex justify-between text-xs support-text">
        {QUANTILE_STOPS.map((s) => (
          <span key={s.key} className="flex flex-col items-center gap-0.5">
            <span>{s.label}</span>
            <span className="text-[var(--color-text)]">{pctSigned(quantiles[s.key])}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

/** `AnalogSummary` from a horizon's already-fetched `MlHorizonForecast`
 * -- no separate `/analogs` request needed, that endpoint returns the
 * same shape per horizon. Evidence, not prophecy: no gauge, no
 * countdown, nothing implying a forecast is being made here. Mean and
 * median are both shown -- their divergence is itself the signal that
 * the analog distribution is skewed, and showing only one would hide
 * that. `is_reliable: false` visibly desaturates the whole panel rather
 * than adding a footnote. */
export function AnalogPanel({ analog, horizonLabel }: { analog: AnalogSummary; horizonLabel: string }) {
  if (analog.sample_size === 0) {
    return (
      <div className="flex flex-col gap-2">
        <h4 className="text-sm font-semibold">Historical Analogs -- {horizonLabel}</h4>
        <EmptyState
          title="No historical analogs found"
          reason="Not enough similar historical setups were found for this horizon."
        />
      </div>
    )
  }

  return (
    <div className={`flex flex-col gap-3 ${analog.is_reliable ? '' : 'opacity-60'}`}>
      <h4 className="text-sm font-semibold">Historical Analogs -- {horizonLabel}</h4>
      {!analog.is_reliable && (
        <p className="support-text text-xs">
          Flagged unreliable by the backend -- small or noisy sample. Figures below are indicative only.
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatWithN label="Mean return" value={pctSigned(analog.mean_return)} sampleSize={analog.sample_size} />
        <StatWithN label="Median return" value={pctSigned(analog.median_return)} sampleSize={analog.sample_size} />
        <StatWithN label="Positive frequency" value={pct(analog.positive_rate)} sampleSize={analog.sample_size} />
        <StatWithN label="Negative frequency" value={pct(analog.negative_rate)} sampleSize={analog.sample_size} />
      </div>
      {analog.quantiles && <QuantileStrip quantiles={analog.quantiles} />}
      <p className="support-text text-xs">
        Historical evidence from similar past setups -- a frequency of past outcomes, not a forecast of what happens next.
      </p>
    </div>
  )
}
