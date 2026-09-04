import { useEffect, useRef } from 'react'
import {
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

Chart.register(CategoryScale, LinearScale, LineController, LineElement, PointElement, Filler, Tooltip, Legend)

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
 * axes. Purely presentational -- computes no new values of its own. */
export function ForecastLineChart({
  historical,
  predicted,
  markers = [],
  referenceLines = [],
}: {
  historical: ForecastChartPoint[]
  predicted: ForecastChartPoint[]
  markers?: ForecastLineChartMarker[]
  referenceLines?: ForecastLineChartReferenceLine[]
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const chartRef = useRef<Chart | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const allDates = Array.from(new Set([...historical.map((p) => p.date), ...predicted.map((p) => p.date), ...markers.map((m) => m.date)])).sort()
    const historicalByDate = new Map(historical.map((p) => [p.date, p.value]))
    const predictedByDate = new Map(predicted.map((p) => [p.date, p.value]))

    const datasets: ChartDataset<'line', (number | null)[]>[] = []

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
  }, [historical, predicted, markers, referenceLines])

  return (
    <div style={{ height: 320 }} role="img" aria-label="Forecast price chart">
      <canvas ref={canvasRef} />
    </div>
  )
}
