import { useEffect, useRef } from 'react'
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  type ChartDataset,
} from 'chart.js'

Chart.register(
  CategoryScale,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  BarController,
  BarElement,
  Filler,
  Tooltip,
  Legend,
)

export interface ForecastChartPoint {
  date: string
  value: number
}

export interface ForecastLineChartMarker {
  label: string
  date: string
  value: number
  color: string
}

export interface ForecastLineChartReferenceLine {
  label: string
  value: number
  color: string
}

export interface ForecastLineChartBandPoint {
  date: string
  low: number
  high: number
}

export interface PriceChartVolumePoint {
  date: string
  value: number
}

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
  const parsed = dateOnly
    ? (() => {
        const [y, m, d] = iso.split('-').map(Number)
        return new Date(y, m - 1, d)
      })()
    : new Date(iso)
  if (Number.isNaN(parsed.getTime())) return iso
  return parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/** Chart.js line chart: all historical closes plus the selected
 * horizon's predicted points, sharing one chronological date axis. Both
 * series are aligned to the same label array with `null` gaps where a
 * series has no point for that date, so Chart.js draws each line only
 * where real data exists -- never interpolating across a gap that
 * isn't real. Markers (other technical methods' single-point
 * projections) and reference lines (moving averages) overlay the same
 * axes. An optional volume series renders as a second, shorter bar
 * chart sharing the same date domain directly below.
 *
 * Extracted (Wave 2, D4) from the two callers that already existed --
 * `ForecastSection` (deterministic forecast) and `MlForecastPanel` (ML
 * forecast) -- into the one shared price-chart component every stock-
 * detail surface uses, rather than a second charting approach. Purely
 * presentational -- computes no new values of its own. */
export function PriceChart({
  historical,
  predicted,
  markers = [],
  referenceLines = [],
  band = [],
  volume = [],
  ariaLabel = 'Price chart',
}: {
  historical: ForecastChartPoint[]
  predicted: ForecastChartPoint[]
  markers?: ForecastLineChartMarker[]
  referenceLines?: ForecastLineChartReferenceLine[]
  /** Optional shaded uncertainty range (e.g. a P10-P90 prediction
   * interval) drawn behind the predicted line, sharing its date axis. */
  band?: ForecastLineChartBandPoint[]
  /** Optional daily volume, rendered as its own bar sub-chart below the
   * price chart, sharing the same date domain. */
  volume?: PriceChartVolumePoint[]
  ariaLabel?: string
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const chartRef = useRef<Chart | null>(null)
  const volumeCanvasRef = useRef<HTMLCanvasElement>(null)
  const volumeChartRef = useRef<Chart | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const allDates = Array.from(
      new Set([
        ...historical.map((p) => p.date),
        ...predicted.map((p) => p.date),
        ...markers.map((m) => m.date),
        ...band.map((b) => b.date),
        ...volume.map((v) => v.date),
      ]),
    ).sort()
    const historicalByDate = new Map(historical.map((p) => [p.date, p.value]))
    const predictedByDate = new Map(predicted.map((p) => [p.date, p.value]))
    const bandLowByDate = new Map(band.map((b) => [b.date, b.low]))
    const bandHighByDate = new Map(band.map((b) => [b.date, b.high]))

    const datasets: ChartDataset<'line', (number | null)[]>[] = []

    if (band.length > 0) {
      // Two invisible-border lines with the upper one filled down to the
      // lower one -- the standard Chart.js "shade the area between two
      // lines" technique -- render the uncertainty range behind
      // everything else.
      datasets.push({
        label: 'Low estimate',
        data: allDates.map((d) => bandLowByDate.get(d) ?? null),
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        pointRadius: 0,
        borderWidth: 0,
        spanGaps: false,
      })
      datasets.push({
        label: 'High estimate',
        data: allDates.map((d) => bandHighByDate.get(d) ?? null),
        borderColor: 'transparent',
        backgroundColor: 'rgba(41, 82, 163, 0.12)',
        pointRadius: 0,
        borderWidth: 0,
        fill: '-1',
        spanGaps: false,
      })
    }

    if (historical.length > 0) {
      datasets.push({
        label: 'Historical',
        data: allDates.map((d) => historicalByDate.get(d) ?? null),
        borderColor: '#9ca3af',
        backgroundColor: '#9ca3af',
        pointRadius: 0,
        pointHoverRadius: 3,
        borderWidth: 2,
        spanGaps: false,
      })
    }

    if (predicted.length > 0) {
      datasets.push({
        label: 'Predicted',
        data: allDates.map((d) => predictedByDate.get(d) ?? null),
        borderColor: '#2952a3',
        backgroundColor: 'rgba(41, 82, 163, 0.15)',
        borderDash: [6, 4],
        pointRadius: 0,
        pointHoverRadius: 3,
        borderWidth: 2.25,
        fill: true,
        spanGaps: false,
      })
    }

    for (const marker of markers) {
      datasets.push({
        label: marker.label,
        data: allDates.map((d) => (d === marker.date ? marker.value : null)),
        borderColor: marker.color,
        backgroundColor: marker.color,
        pointRadius: 5,
        pointHoverRadius: 6,
        showLine: false,
        spanGaps: false,
      })
    }

    chartRef.current?.destroy()
    chartRef.current = new Chart(canvas, {
      type: 'line',
      data: { labels: allDates.map(formatAxisDate), datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const value = ctx.parsed.y
                return value === null ? undefined : `${ctx.dataset.label}: ${value.toFixed(2)}`
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
          y: {
            grid: { color: 'rgba(148, 163, 184, 0.15)' },
            afterDataLimits: (scale) => {
              for (const ref of referenceLines) {
                if (ref.value < scale.min) scale.min = ref.value
                if (ref.value > scale.max) scale.max = ref.value
              }
              const pad = (scale.max - scale.min) * 0.08 || 1
              scale.min -= pad
              scale.max += pad
            },
          },
        },
      },
      plugins: [
        {
          id: 'referenceLines',
          afterDraw(chartInstance) {
            const { ctx, chartArea, scales } = chartInstance
            for (const ref of referenceLines) {
              const y = scales.y.getPixelForValue(ref.value)
              ctx.save()
              ctx.strokeStyle = ref.color
              ctx.setLineDash([3, 3])
              ctx.globalAlpha = 0.7
              ctx.beginPath()
              ctx.moveTo(chartArea.left, y)
              ctx.lineTo(chartArea.right, y)
              ctx.stroke()
              ctx.setLineDash([])
              ctx.globalAlpha = 1
              ctx.fillStyle = ref.color
              ctx.font = '9px sans-serif'
              ctx.textAlign = 'right'
              ctx.fillText(ref.label, chartArea.right, y - 4)
              ctx.restore()
            }
          },
        },
      ],
    })

    return () => {
      chartRef.current?.destroy()
      chartRef.current = null
    }
  }, [historical, predicted, markers, referenceLines, band, volume])

  useEffect(() => {
    const canvas = volumeCanvasRef.current
    volumeChartRef.current?.destroy()
    volumeChartRef.current = null
    if (!canvas || volume.length === 0) return

    const allDates = Array.from(new Set(volume.map((v) => v.date))).sort()
    const volumeByDate = new Map(volume.map((v) => [v.date, v.value]))

    volumeChartRef.current = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: allDates.map(formatAxisDate),
        datasets: [
          {
            label: 'Volume',
            data: allDates.map((d) => volumeByDate.get(d) ?? null),
            backgroundColor: 'rgba(148, 163, 184, 0.45)',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const value = ctx.parsed.y
                return value === null ? undefined : `Volume: ${value.toLocaleString()}`
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
          y: { grid: { color: 'rgba(148, 163, 184, 0.1)' }, ticks: { maxTicksLimit: 3 } },
        },
      },
    })

    return () => {
      volumeChartRef.current?.destroy()
      volumeChartRef.current = null
    }
  }, [volume])

  return (
    <div className="flex flex-col gap-1">
      <div style={{ height: volume.length > 0 ? 260 : 320 }} role="img" aria-label={ariaLabel}>
        <canvas ref={canvasRef} />
      </div>
      {volume.length > 0 && (
        <div style={{ height: 80 }} role="img" aria-label={`${ariaLabel} volume`}>
          <canvas ref={volumeCanvasRef} />
        </div>
      )}
    </div>
  )
}
