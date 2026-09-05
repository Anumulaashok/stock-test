import { useEffect, useRef } from 'react'
import { Chart, Legend, LinearScale, PointElement, ScatterController, Tooltip } from 'chart.js'
import { readChartColors } from '../../lib/chartTheme'
import { useTheme } from '../../theme/ThemeContext'

Chart.register(ScatterController, LinearScale, PointElement, Tooltip, Legend)

export interface AccuracyScatterPoint {
  targetDate: string
  predictedReturn: number
  actualReturn: number
  directionCorrect: boolean | null
}

const CORRECT_COLOR = '#2f9e5c'
const INCORRECT_COLOR = '#c94f3d'
const NEUTRAL_COLOR = '#8b93b8'
const QUADRANT_FILL_CORRECT = 'rgba(53, 210, 154, 0.06)'
const QUADRANT_FILL_INCORRECT = 'rgba(255, 107, 107, 0.06)'

/** Below this many resolved points, quadrant shading is suppressed --
 * shading implies a distribution, and at n<10 that distribution isn't
 * really there yet (I9: refuse the inference, not the data). Points
 * themselves always render regardless of n; only the chrome is gated. */
export const MIN_N_FOR_QUADRANT_SHADING = 10

/** Splits points into correct/incorrect/unclassified using ONLY the
 * backend's own `directionCorrect` field -- never a recomputed sign
 * comparison. This is the single authority for a point's color and
 * marker shape; the quadrant background is decoration derived
 * independently from axis geometry and can legitimately disagree with a
 * point sitting near zero (e.g. `predicted_return === 0`, which the
 * backend's `(actual_return > 0) == (predicted_return > 0)` rule treats
 * as "not positive"). A point's own color always wins over where it
 * geometrically falls. */
export function partitionByDirection(points: AccuracyScatterPoint[]): {
  correct: AccuracyScatterPoint[]
  incorrect: AccuracyScatterPoint[]
  unclassified: AccuracyScatterPoint[]
} {
  return {
    correct: points.filter((p) => p.directionCorrect === true),
    incorrect: points.filter((p) => p.directionCorrect === false),
    unclassified: points.filter((p) => p.directionCorrect === null),
  }
}

/** Predicted-return vs actual-return scatter with a 45deg identity line.
 * Quadrant shading (top-right/bottom-left = directionally correct by
 * axis geometry) is illustrative only and gated on `MIN_N_FOR_QUADRANT_SHADING`
 * -- the authoritative correct/incorrect classification is each point's
 * own color and shape, from `directionCorrect`, never recomputed here. */
export function AccuracyScatterChart({ points }: { points: AccuracyScatterPoint[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const chartRef = useRef<Chart | null>(null)
  const { theme } = useTheme()

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const colors = readChartColors()

    const allValues = points.flatMap((p) => [p.predictedReturn, p.actualReturn])
    const rawExtent = allValues.length > 0 ? Math.max(...allValues.map(Math.abs)) : 0.05
    // Pad and floor the axis extent so a single near-zero point (or an
    // empty set) still renders a legible, non-degenerate square axis.
    const extent = Math.max(rawExtent * 1.2, 0.02)
    const showQuadrants = points.length >= MIN_N_FOR_QUADRANT_SHADING

    const { correct, incorrect, unclassified } = partitionByDirection(points)
    const toXY = (pts: AccuracyScatterPoint[]) => pts.map((p) => ({ x: p.predictedReturn, y: p.actualReturn }))

    chartRef.current?.destroy()
    chartRef.current = new Chart(canvas, {
      type: 'scatter',
      data: {
        datasets: [
          {
            label: 'Directionally correct',
            data: toXY(correct),
            backgroundColor: CORRECT_COLOR,
            borderColor: colors.pointBorder,
            borderWidth: 1,
            pointStyle: 'circle',
            pointRadius: 4,
            pointHoverRadius: 6,
          },
          {
            label: 'Directionally wrong',
            data: toXY(incorrect),
            backgroundColor: INCORRECT_COLOR,
            borderColor: colors.pointBorder,
            borderWidth: 1,
            pointStyle: 'triangle',
            pointRadius: 5,
            pointHoverRadius: 7,
          },
          // Rarer than the other two categories and easy to lose against
          // the dark ground/grid, especially near the zero-return
          // origin where the diagonal and quadrant boundary both cross
          // -- a brighter fill and a visible border, plus a slightly
          // larger radius, keep it findable rather than blending in.
          ...(unclassified.length > 0
            ? [
                {
                  label: 'Unclassified',
                  data: toXY(unclassified),
                  backgroundColor: NEUTRAL_COLOR,
                  borderColor: colors.pointBorder,
                  borderWidth: 1.5,
                  pointStyle: 'rect',
                  pointRadius: 5,
                  pointHoverRadius: 7,
                },
              ]
            : []),
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        aspectRatio: 1,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 }, usePointStyle: true, color: colors.tick } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const p = ctx.raw as { x: number; y: number }
                return `Predicted ${(p.x * 100).toFixed(1)}% · Actual ${(p.y * 100).toFixed(1)}%`
              },
            },
          },
        },
        scales: {
          x: {
            type: 'linear',
            min: -extent,
            max: extent,
            title: { display: true, text: 'Predicted return', font: { size: 10 } },
            ticks: { callback: (v) => `${(Number(v) * 100).toFixed(0)}%`, font: { size: 9 }, color: colors.tick },
            grid: { color: colors.grid },
          },
          y: {
            type: 'linear',
            min: -extent,
            max: extent,
            title: { display: true, text: 'Actual return', font: { size: 10 } },
            ticks: { callback: (v) => `${(Number(v) * 100).toFixed(0)}%`, font: { size: 9 }, color: colors.tick },
            grid: { color: colors.grid },
          },
        },
      },
      plugins: [
        {
          id: 'identityLineAndQuadrants',
          beforeDatasetsDraw(chartInstance) {
            const { ctx, chartArea, scales } = chartInstance
            const { left, right, top, bottom } = chartArea
            const zeroX = scales.x.getPixelForValue(0)
            const zeroY = scales.y.getPixelForValue(0)

            if (showQuadrants) {
              ctx.save()
              ctx.fillStyle = QUADRANT_FILL_CORRECT
              ctx.fillRect(zeroX, top, right - zeroX, zeroY - top) // predicted up, actual up
              ctx.fillRect(left, zeroY, zeroX - left, bottom - zeroY) // predicted down, actual down
              ctx.fillStyle = QUADRANT_FILL_INCORRECT
              ctx.fillRect(left, top, zeroX - left, zeroY - top) // predicted down, actual up
              ctx.fillRect(zeroX, zeroY, right - zeroX, bottom - zeroY) // predicted up, actual down
              ctx.restore()
            }

            ctx.save()
            ctx.strokeStyle = colors.quadrantLine
            ctx.setLineDash([4, 4])
            ctx.beginPath()
            ctx.moveTo(scales.x.getPixelForValue(-extent), scales.y.getPixelForValue(-extent))
            ctx.lineTo(scales.x.getPixelForValue(extent), scales.y.getPixelForValue(extent))
            ctx.stroke()
            ctx.restore()
          },
        },
      ],
    })

    return () => {
      chartRef.current?.destroy()
      chartRef.current = null
    }
  }, [points, theme])

  return (
    <div style={{ height: 220 }} role="img" aria-label="Predicted versus actual return scatter">
      <canvas ref={canvasRef} />
    </div>
  )
}
