export interface ForecastLineChartSeries {
  label: string
  color: string
  points: { day: number; value: number }[]
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

const CHART_WIDTH = 560
const CHART_HEIGHT = 220
const PADDING_LEFT = 56
const PADDING_RIGHT = 16
const PADDING_TOP = 12
const PADDING_BOTTOM = 28

/** A dependency-free SVG line chart for forecast series. Plots one or
 * more day->price series on shared axes, plus optional single-point
 * markers (e.g. other methods' projections) and horizontal reference
 * lines (e.g. moving averages) -- purely presentational, computes no
 * new values of its own. */
export function ForecastLineChart({
  series,
  markers = [],
  referenceLines = [],
}: {
  series: ForecastLineChartSeries[]
  markers?: ForecastLineChartMarker[]
  referenceLines?: ForecastLineChartReferenceLine[]
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

  const minValue = Math.min(...allValues)
  const maxValue = Math.max(...allValues)
  const valueSpan = maxValue - minValue || Math.max(1, maxValue * 0.1) || 1
  const minDay = Math.min(0, ...allDays)
  const maxDay = Math.max(...allDays)
  const daySpan = maxDay - minDay || 1

  const plotWidth = CHART_WIDTH - PADDING_LEFT - PADDING_RIGHT
  const plotHeight = CHART_HEIGHT - PADDING_TOP - PADDING_BOTTOM

  const x = (day: number) => PADDING_LEFT + ((day - minDay) / daySpan) * plotWidth
  const y = (value: number) => PADDING_TOP + plotHeight - ((value - minValue) / valueSpan) * plotHeight

  const yTicks = [minValue, minValue + valueSpan / 2, maxValue]

  return (
    <svg
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      className="w-full"
      role="img"
      aria-label="Forecast price chart"
    >
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
          <text x={PADDING_LEFT - 6} y={y(tick)} textAnchor="end" dominantBaseline="middle" className="fill-current text-[9px]" style={{ fill: 'var(--color-text-faint)' }}>
            {tick.toFixed(0)}
          </text>
        </g>
      ))}

      {referenceLines.map((ref) => (
        <g key={ref.label}>
          <line
            x1={PADDING_LEFT}
            x2={CHART_WIDTH - PADDING_RIGHT}
            y1={y(ref.value)}
            y2={y(ref.value)}
            stroke={ref.color}
            strokeDasharray="4 3"
            strokeWidth={1}
          />
          <text x={CHART_WIDTH - PADDING_RIGHT} y={y(ref.value) - 3} textAnchor="end" className="text-[9px]" style={{ fill: ref.color }}>
            {ref.label}
          </text>
        </g>
      ))}

      {series.map((s) =>
        s.points.length > 0 ? (
          <g key={s.label}>
            <polyline
              fill="none"
              stroke={s.color}
              strokeWidth={2}
              points={s.points.map((p) => `${x(p.day)},${y(p.value)}`).join(' ')}
            />
            {s.points.map((p) => (
              <circle key={p.day} cx={x(p.day)} cy={y(p.value)} r={2.5} fill={s.color} />
            ))}
          </g>
        ) : null,
      )}

      {markers.map((m) => (
        <g key={m.label}>
          <circle cx={x(m.day)} cy={y(m.value)} r={3.5} fill={m.color} stroke="var(--color-surface)" strokeWidth={1} />
        </g>
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
