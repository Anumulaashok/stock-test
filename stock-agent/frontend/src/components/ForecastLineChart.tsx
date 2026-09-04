export interface ForecastLineChartSeries {
  label: string
  color: string
  points: { day: number; value: number }[]
  /** Presentational only: renders this series dashed instead of solid (used for the forecast leg). */
  dashed?: boolean
  /** Presentational only: fills the area under this series with a soft gradient (used for the forecast leg). */
  area?: boolean
}

export interface ForecastLineChartMarker {
  label: string
  day: number
  value: number
  color: string
}

export interface ForecastLineChartReferenceLine {
  label: string
  value: number
  color: string
}

const CHART_WIDTH = 720
const CHART_HEIGHT = 320
const PADDING_LEFT = 60
const PADDING_RIGHT = 20
const PADDING_TOP = 16
const PADDING_BOTTOM = 30

function formatTick(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 1000) return value.toFixed(0)
  if (abs >= 100) return value.toFixed(0)
  return value.toFixed(2)
}

/** A dependency-free SVG line chart for forecast series. Plots one or
 * more day->price series on shared axes, plus optional single-point
 * markers (e.g. other methods' projections) and horizontal reference
 * lines (e.g. moving averages) -- purely presentational, computes no
 * new values of its own. */
export function formatAxisDate(iso: string): string {
  // Handles both a plain date ("2026-07-24") and a full ISO datetime
  // ("2026-07-24T00:00:00+05:30", e.g. from a provider's timestamp).
  // A plain date must go through the local-time constructor (`new
  // Date(iso)` parses a bare date as UTC midnight, which shifts a day
  // back in any timezone behind UTC); a full datetime already carries
  // its own offset, so `new Date(iso)` is correct for that case -- and
  // required, since a manual "split on '-'" parse breaks on it (the day
  // segment carries the time/offset too), silently falling back to the
  // raw, unformatted -- and axis-clipping-long -- string.
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(iso)
  const parsed = dateOnly ? (() => {
    const [y, m, d] = iso.split('-').map(Number)
    return new Date(y, m - 1, d)
  })() : new Date(iso)
  if (Number.isNaN(parsed.getTime())) return iso
  return parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function ForecastLineChart({
  series,
  markers = [],
  referenceLines = [],
  dateLabels = {},
}: {
  series: ForecastLineChartSeries[]
  markers?: ForecastLineChartMarker[]
  referenceLines?: ForecastLineChartReferenceLine[]
  /** Real calendar date (ISO `YYYY-MM-DD`) for a given `day` offset, so
   * the x-axis can show "Sep 4" instead of an abstract "+3". Days with
   * no known date (e.g. "today" when the report carries no date for
   * the current price) fall back to the relative label. */
  dateLabels?: Record<number, string>
}) {
  const allValues = [
    ...series.flatMap((s) => s.points.map((p) => p.value)),
    ...markers.map((m) => m.value),
    ...referenceLines.map((r) => r.value),
  ]
  const allDays = [...series.flatMap((s) => s.points.map((p) => p.day)), ...markers.map((m) => m.day)]

  if (allValues.length === 0 || allDays.length === 0) {
    return null
  }

  const rawMin = Math.min(...allValues)
  const rawMax = Math.max(...allValues)
  const pad = (rawMax - rawMin) * 0.08 || Math.max(1, rawMax * 0.05) || 1
  const minValue = rawMin - pad
  const maxValue = rawMax + pad
  const valueSpan = maxValue - minValue || 1
  const minDay = Math.min(0, ...allDays)
  const maxDay = Math.max(...allDays)
  const daySpan = maxDay - minDay || 1

  const plotWidth = CHART_WIDTH - PADDING_LEFT - PADDING_RIGHT
  const plotHeight = CHART_HEIGHT - PADDING_TOP - PADDING_BOTTOM

  const x = (day: number) => PADDING_LEFT + ((day - minDay) / daySpan) * plotWidth
  const y = (value: number) => PADDING_TOP + plotHeight - ((value - minValue) / valueSpan) * plotHeight

  const yTicks = [minValue + valueSpan * 0.9, minValue + valueSpan * 0.65, minValue + valueSpan * 0.4, minValue + valueSpan * 0.15]

  // Sparse, non-overlapping day-axis ticks: first, last, and a few in between.
  const xTickDays = Array.from(new Set([minDay, Math.round(minDay + daySpan / 2), maxDay]))

  return (
    <svg
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      className="w-full"
      role="img"
      aria-label="Forecast price chart"
    >
      <defs>
        {series.map(
          (s) =>
            s.area && (
              <linearGradient key={`grad-${s.label}`} id={`grad-${s.label.replace(/\s+/g, '-')}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity="0.22" />
                <stop offset="100%" stopColor={s.color} stopOpacity="0" />
              </linearGradient>
            ),
        )}
      </defs>

      {yTicks.map((tick, i) => (
        <g key={i}>
          <line
            x1={PADDING_LEFT}
            x2={CHART_WIDTH - PADDING_RIGHT}
            y1={y(tick)}
            y2={y(tick)}
            stroke="var(--color-border)"
            strokeWidth={1}
          />
          <text
            x={PADDING_LEFT - 8}
            y={y(tick)}
            textAnchor="end"
            dominantBaseline="middle"
            className="text-[10px] tabular-nums"
            style={{ fill: 'var(--color-text-faint)' }}
          >
            {formatTick(tick)}
          </text>
        </g>
      ))}

      {/* Divider marking where history ends and the forecast begins. */}
      {minDay < 0 && maxDay > 0 && (
        <line x1={x(0)} x2={x(0)} y1={PADDING_TOP} y2={CHART_HEIGHT - PADDING_BOTTOM} stroke="var(--color-border-strong)" strokeDasharray="2 3" strokeWidth={1} />
      )}

      {referenceLines.map((ref) => (
        <g key={ref.label}>
          <line
            x1={PADDING_LEFT}
            x2={CHART_WIDTH - PADDING_RIGHT}
            y1={y(ref.value)}
            y2={y(ref.value)}
            stroke={ref.color}
            strokeDasharray="3 3"
            strokeWidth={1}
            opacity={0.7}
          />
          <text x={CHART_WIDTH - PADDING_RIGHT} y={y(ref.value) - 4} textAnchor="end" className="text-[9px] font-medium" style={{ fill: ref.color }}>
            {ref.label}
          </text>
        </g>
      ))}

      {series.map((s) =>
        s.points.length > 0 ? (
          <g key={s.label}>
            {s.area && (
              <polygon
                fill={`url(#grad-${s.label.replace(/\s+/g, '-')})`}
                points={
                  `${x(s.points[0].day)},${CHART_HEIGHT - PADDING_BOTTOM} ` +
                  s.points.map((p) => `${x(p.day)},${y(p.value)}`).join(' ') +
                  ` ${x(s.points[s.points.length - 1].day)},${CHART_HEIGHT - PADDING_BOTTOM}`
                }
              />
            )}
            <polyline
              fill="none"
              stroke={s.color}
              strokeWidth={s.dashed ? 2.25 : 2}
              strokeDasharray={s.dashed ? '6 4' : undefined}
              strokeLinejoin="round"
              strokeLinecap="round"
              points={s.points.map((p) => `${x(p.day)},${y(p.value)}`).join(' ')}
            />
            {s.points.map((p) => (
              <circle key={p.day} cx={x(p.day)} cy={y(p.value)} r={s.dashed ? 2 : 1.75} fill={s.color}>
                <title>{`${dateLabels[p.day] ? formatAxisDate(dateLabels[p.day]) + ' · ' : ''}${s.label}: ${formatTick(p.value)}`}</title>
              </circle>
            ))}
            {/* Emphasized endpoint -- the value the reader's eye lands on first. */}
            <circle cx={x(s.points[s.points.length - 1].day)} cy={y(s.points[s.points.length - 1].value)} r={4} fill="var(--color-surface)" stroke={s.color} strokeWidth={2} />
          </g>
        ) : null,
      )}

      {markers.map((m) => (
        <g key={m.label}>
          <circle cx={x(m.day)} cy={y(m.value)} r={3.5} fill={m.color} stroke="var(--color-surface)" strokeWidth={1.5}>
            <title>{`${m.label}: ${formatTick(m.value)}`}</title>
          </circle>
        </g>
      ))}

      {xTickDays.map((day) => (
        <text key={day} x={x(day)} y={CHART_HEIGHT - PADDING_BOTTOM + 16} textAnchor="middle" className="text-[10px]" style={{ fill: 'var(--color-text-faint)' }}>
          {dateLabels[day] ? formatAxisDate(dateLabels[day]) : day === 0 ? 'Today' : day > 0 ? `+${day}` : `${day}`}
        </text>
      ))}

      <line
        x1={PADDING_LEFT}
        x2={CHART_WIDTH - PADDING_RIGHT}
        y1={CHART_HEIGHT - PADDING_BOTTOM}
        y2={CHART_HEIGHT - PADDING_BOTTOM}
        stroke="var(--color-border-strong)"
        strokeWidth={1}
      />
    </svg>
  )
}
