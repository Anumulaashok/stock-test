import { useState } from 'react'
import type {
  ForecastHorizonKey,
  ReportForecastMetric,
  ReportForecastSection,
  ReportHistoricalPricePoint,
  ReportHorizonForecast,
  ReportMarketSection,
  ReportTechnicalMethod,
  ReportValuationScenario,
} from '../types/backend'
import { humanizeKey } from '../lib/format'
import { MetricStatusBadge } from './StatusBadge'
import { ForecastLineChart, type ForecastLineChartMarker, type ForecastLineChartReferenceLine, type ForecastLineChartSeries } from './ForecastLineChart'

const SCENARIO_LABEL: Record<string, string> = {
  bear: 'Bear',
  base: 'Base',
  bull: 'Bull',
}

const CROSSOVER_LABEL: Record<string, string> = {
  golden_cross: 'Golden cross (bullish)',
  death_cross: 'Death cross (bearish)',
  neutral: 'Neutral',
}

const METHOD_COLORS = ['#2952a3', '#b5540a', '#3a6b35', '#8a6d00', '#7a3ab3']

const HORIZON_TABS: { key: ForecastHorizonKey; label: string }[] = [
  { key: 'daily', label: 'Daily' },
  { key: 'weekly', label: 'Weekly' },
  { key: 'monthly', label: 'Monthly' },
]

// How many trailing historical closes to sample per horizon, and the
// stride used to downsample daily closes into weekly/monthly points --
// this is a purely presentational sampling of already-computed closes
// (never a new calculated value) so the historical segment lines up on
// the same period axis as that horizon's forecast points.
const HORIZON_HISTORY_STEP: Record<ForecastHorizonKey, number> = { daily: 1, weekly: 5, monthly: 21 }
const HORIZON_HISTORY_MAX_POINTS: Record<ForecastHorizonKey, number> = { daily: 30, weekly: 12, monthly: 12 }

function toNumber(value: string | null): number | null {
  if (value === null) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/** Presentational-only percent change between two already-computed
 * prices (never a new financial metric of its own). */
function percentChange(from: number | null, to: number | null): number | null {
  if (from === null || to === null || from === 0) return null
  return ((to - from) / from) * 100
}

function formatSignedPercent(value: number | null): string | null {
  if (value === null) return null
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

/** Downsamples already-observed closing prices into one point per
 * period, ending at period -1 (the period immediately before the
 * forecast's period 0/"today" anchor). Pure and presentation-only --
 * it never fabricates a value, only picks which already-computed
 * closes to plot. Exported for unit testing. */
export function sampleHistoricalPrices(
  historicalPrices: ReportHistoricalPricePoint[],
  horizon: ForecastHorizonKey,
): { day: number; value: number }[] {
  return sampleHistoricalPoints(historicalPrices, horizon).map(({ day, value }) => ({ day, value }))
}

/** Same sampling as `sampleHistoricalPrices`, but keeps each point's
 * real calendar date alongside it (dropped by the function above to
 * keep its existing tested shape) -- used only to label the chart's
 * x-axis with actual dates instead of relative day offsets. */
function sampleHistoricalPoints(
  historicalPrices: ReportHistoricalPricePoint[],
  horizon: ForecastHorizonKey,
): { day: number; value: number; date: string | null }[] {
  const closes = historicalPrices
    .map((p) => ({ date: p.date, value: toNumber(p.close) }))
    .filter((p): p is { date: string; value: number } => p.value !== null)
  if (closes.length === 0) return []

  const step = HORIZON_HISTORY_STEP[horizon]
  const maxPoints = HORIZON_HISTORY_MAX_POINTS[horizon]

  // Sample every `step`-th close counting backward from the most recent
  // one (so the most recent close is always included), capped at
  // `maxPoints`, then restore chronological order.
  const sampled: { value: number; date: string | null }[] = []
  for (let i = closes.length - 1; i >= 0 && sampled.length < maxPoints; i -= step) {
    sampled.push(closes[i])
  }
  sampled.reverse()

  return sampled.map((point, index) => ({ day: index - sampled.length, value: point.value, date: point.date }))
}

/** Builds one chart marker per non-trend technical method, positioned
 * at that method's `horizon_period` -- the same unit the price-trend
 * series' `period` field uses -- so a method's marker lines up with
 * the trend line regardless of horizon. Exported for unit testing. */
export function buildMethodMarkers(methods: ReportTechnicalMethod[]): ForecastLineChartMarker[] {
  const otherMethods = methods.filter((m) => m.method !== 'linear_regression' && m.status === 'calculated')
  return otherMethods
    .map((m, i) => {
      const value = toNumber(m.projected_price)
      return value === null
        ? null
        : { label: humanizeKey(m.method), day: m.horizon_period, value, color: METHOD_COLORS[(i + 1) % METHOD_COLORS.length] }
    })
    .filter((m): m is ForecastLineChartMarker => m !== null)
}

function ForecastMetricCard({ metric }: { metric: ReportForecastMetric }) {
  return (
    <div className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-[var(--color-text-muted)]">{humanizeKey(metric.name)}</span>
        {metric.status !== 'calculated' && <MetricStatusBadge status={metric.status} />}
      </div>
      {metric.status === 'calculated' ? (
        <>
          <div className="mt-1 text-xs text-[var(--color-text-faint)]">
            Historical CAGR: <span className="font-mono-nums">{metric.formatted_historical_cagr}</span>
          </div>
          <dl className="mt-2 space-y-0.5 border-t border-[var(--color-border)] pt-2 text-xs">
            {metric.projections.map((year) => (
              <div key={year.year_offset} className="flex justify-between gap-2">
                <dt className="text-[var(--color-text-faint)]">Year +{year.year_offset}</dt>
                <dd className="font-mono-nums">{year.formatted_value ?? 'unavailable'}</dd>
              </div>
            ))}
          </dl>
        </>
      ) : (
        <p className="mt-1 text-xs text-[var(--color-text-faint)]">{metric.reason}</p>
      )}
    </div>
  )
}

function ValuationScenarioRow({ scenario }: { scenario: ReportValuationScenario }) {
  return (
    <div className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-[var(--color-text-muted)]">
          {SCENARIO_LABEL[scenario.scenario] ?? humanizeKey(scenario.scenario)}
        </span>
        {scenario.status !== 'calculated' && <MetricStatusBadge status={scenario.status} />}
      </div>
      <div className="mt-1 font-mono-nums text-xl font-semibold">
        {scenario.formatted_value_per_share ?? (
          <span className="text-base font-normal text-[var(--color-text-faint)]">Unavailable</span>
        )}
      </div>
      {scenario.fcf_growth_rate !== null && (
        <div className="text-xs text-[var(--color-text-faint)]">
          FCF growth assumption: <span className="font-mono-nums">{scenario.fcf_growth_rate}</span>
        </div>
      )}
      {scenario.reason && scenario.status !== 'calculated' && (
        <p className="mt-1 text-xs text-[var(--color-text-faint)]">{scenario.reason}</p>
      )}
    </div>
  )
}

function HorizonTabs({ active, onSelect }: { active: ForecastHorizonKey; onSelect: (horizon: ForecastHorizonKey) => void }) {
  return (
    <div
      role="tablist"
      aria-label="Forecast horizon"
      className="inline-flex rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-0.5"
    >
      {HORIZON_TABS.map((tab) => {
        const isActive = tab.key === active
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onSelect(tab.key)}
            className={
              'rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors ' +
              (isActive
                ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]'
                : 'text-[var(--color-text-faint)] hover:text-[var(--color-text-muted)]')
            }
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

/** Compact checkbox toggle for a chart overlay -- pure display-state,
 * never touches which data exists, only what the chart currently draws. */
function IndicatorToggle({ id, label, checked, onChange }: { id: string; label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label htmlFor={id} className="flex items-center gap-2 px-2.5 py-1.5 text-xs text-[var(--color-text-muted)] hover:bg-[var(--color-accent-soft)]">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-3.5 w-3.5 rounded border-[var(--color-border-strong)] accent-[var(--color-accent)]"
      />
      {label}
    </label>
  )
}

function IndicatorsMenu({
  showSma,
  onShowSmaChange,
  showMethods,
  onShowMethodsChange,
}: {
  showSma: boolean
  onShowSmaChange: (v: boolean) => void
  showMethods: boolean
  onShowMethodsChange: (v: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-muted)] hover:border-[var(--color-border-strong)]"
      >
        Indicators ▾
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-1 w-48 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] py-1 shadow-[var(--shadow-md,0_4px_16px_rgba(0,0,0,0.12))]">
          <IndicatorToggle id="ind-sma" label="Moving averages (SMA)" checked={showSma} onChange={onShowSmaChange} />
          <IndicatorToggle id="ind-methods" label="Other technical methods" checked={showMethods} onChange={onShowMethodsChange} />
        </div>
      )}
    </div>
  )
}

function ForecastDataDrawer({ points }: { points: ReportHorizonForecast['price_trend'] }) {
  const [open, setOpen] = useState(false)
  if (points.length === 0) return null
  return (
    <details className="mt-3 border-t border-[var(--color-border)] pt-2" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className="cursor-pointer text-xs font-medium text-[var(--color-accent)] hover:text-[var(--color-accent-strong)]">
        {open ? 'Hide forecast data' : 'View forecast data'}
      </summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[240px] text-left text-xs">
          <thead>
            <tr className="text-[var(--color-text-faint)]">
              <th className="py-1 font-medium">Forecast point</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.period} className="border-t border-[var(--color-border)]">
                <td className="py-1 font-mono-nums text-[var(--color-text-muted)]">
                  {point.date ?? `Period ${point.period}`}: {point.formatted_projected_price ?? 'unavailable'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

function TrendStatusBanner({ signal }: { signal: ReportHorizonForecast['technical_signal'] }) {
  if (!signal) return null
  const dotColor =
    signal.color === 'green'
      ? 'var(--color-status-positive)'
      : signal.color === 'red'
        ? 'var(--color-status-negative)'
        : signal.color === 'yellow'
          ? 'var(--color-status-medium)'
          : 'var(--color-status-info)'
  const label = signal.label === 'bullish' ? 'Bullish' : signal.label === 'bearish' ? 'Bearish' : signal.label === 'mixed' ? 'Mixed signals' : signal.label === 'neutral' ? 'Neutral' : 'Unavailable'
  return (
    <div className="flex items-start gap-2 rounded-md border border-[var(--color-border)] bg-[var(--color-accent-soft)]/40 px-3 py-2">
      <span aria-hidden className="mt-1 h-2 w-2 shrink-0 rounded-full" style={{ background: dotColor }} />
      <p className="text-xs leading-snug text-[var(--color-text-muted)]">
        <span className="font-semibold uppercase tracking-wide" style={{ color: dotColor }}>
          {label}
        </span>{' '}
        — {signal.reason}
      </p>
    </div>
  )
}

function TechnicalSignalsStrip({ data }: { data: ReportHorizonForecast }) {
  const cells: { label: string; value: string; tone: 'up' | 'down' | 'neutral' }[] = []

  data.moving_averages.forEach((ma) => {
    cells.push({
      label: `${ma.window}-day SMA`,
      value: ma.status === 'calculated' ? (ma.formatted_value ?? 'unavailable') : 'unavailable',
      tone: 'neutral',
    })
  })

  if (data.crossover) {
    const signal = data.crossover.status === 'calculated' ? data.crossover.signal : null
    cells.push({
      label: 'Crossover',
      value: signal ? (CROSSOVER_LABEL[signal] ?? signal) : (data.crossover.reason ?? 'unavailable'),
      tone: signal === 'golden_cross' ? 'up' : signal === 'death_cross' ? 'down' : 'neutral',
    })
  }

  data.technical_methods.forEach((method) => {
    cells.push({
      label: humanizeKey(method.method),
      value: method.status === 'calculated' ? (method.formatted_projected_price ?? 'unavailable') : (method.reason ?? 'unavailable'),
      tone: 'neutral',
    })
  })

  if (cells.length === 0) return null

  const toneClass: Record<(typeof cells)[number]['tone'], string> = {
    up: 'text-[var(--color-status-positive)]',
    down: 'text-[var(--color-status-negative)]',
    neutral: 'text-[var(--color-text)]',
  }

  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">Technical Signals</h3>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {cells.map((cell) => (
          <div key={cell.label} className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">{cell.label}</div>
            <div className={`mt-0.5 text-sm font-semibold ${toneClass[cell.tone]}`}>{cell.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

/** When the deterministic price-trend line has no data, fall back to the
 * first calculated technical method (e.g. SMA-crossover momentum) as the
 * headline "what are we predicting" figure instead of leaving the
 * summary panel blank -- never fabricated, always labeled with which
 * method actually produced it, and never `linear_regression` (that IS
 * the price-trend line; if it were calculated, `lastPoint` above would
 * already be set). */
function pickHeadlineMethod(methods: ReportTechnicalMethod[]): ReportTechnicalMethod | null {
  return methods.find((m) => m.status === 'calculated' && m.method !== 'linear_regression') ?? null
}

/** True when the backend's own reason for having nothing to show points
 * at a fixable data gap (insufficient stored price history) rather than
 * a structural unavailability -- used only to decide whether to add a
 * pointer to the historical-import tool that actually fixes it. */
function isFixableWithHistoricalImport(reason: string | null): boolean {
  return reason !== null && /historical (price|closing price)/i.test(reason)
}

function ForecastSummaryPanel({
  data,
  currentPrice,
}: {
  data: ReportHorizonForecast
  currentPrice: number | null
}) {
  const lastPoint = data.price_trend.length > 0 ? data.price_trend[data.price_trend.length - 1] : null
  const headlineMethod = lastPoint ? null : pickHeadlineMethod(data.technical_methods)
  const formattedTarget = lastPoint ? lastPoint.formatted_projected_price : headlineMethod?.formatted_projected_price ?? null
  const targetValue = lastPoint
    ? toNumber(lastPoint.projected_price)
    : headlineMethod
      ? toNumber(headlineMethod.projected_price)
      : null
  const potential = percentChange(currentPrice, targetValue)
  const potentialLabel = formatSignedPercent(potential)

  const reason = data.price_trend_reason
  const showHistoricalImportHint = !lastPoint && !headlineMethod && isFixableWithHistoricalImport(reason)

  return (
    <div className="flex flex-col gap-3 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">Forecast Summary</h3>
      {lastPoint || headlineMethod ? (
        <>
          <div>
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">
              {lastPoint ? 'Expected' : 'Predicted'}
            </div>
            <div className="font-mono-nums text-2xl font-semibold text-[var(--color-text)]">
              {formattedTarget ?? 'unavailable'}
            </div>
            {headlineMethod && (
              <div className="mt-0.5 text-[10px] text-[var(--color-text-faint)]">via {humanizeKey(headlineMethod.method)}</div>
            )}
          </div>
          {potentialLabel && (
            <div>
              <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">Potential</div>
              <div className={`font-mono-nums text-sm font-semibold ${potential !== null && potential >= 0 ? 'text-[var(--color-status-positive)]' : 'text-[var(--color-status-negative)]'}`}>
                {potentialLabel}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="flex flex-col gap-1.5">
          <p className="text-xs text-[var(--color-text-faint)]">{reason ?? 'Forecast unavailable for this horizon.'}</p>
          {showHistoricalImportHint && (
            <p className="text-xs text-[var(--color-text-faint)]">
              Import this ticker's price history in{' '}
              <a href="/settings/system" className="font-medium text-[var(--color-accent-strong)] hover:underline">
                Settings → System
              </a>{' '}
              to unlock this.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function HorizonForecastPanel({
  data,
  currentPrice,
  historicalPrices,
}: {
  data: ReportHorizonForecast
  currentPrice: number | null
  historicalPrices: ReportHistoricalPricePoint[]
}) {
  const [showSma, setShowSma] = useState(true)
  const [showMethods, setShowMethods] = useState(true)

  const trendPoints = data.price_trend
    .map((point) => ({ day: point.period, value: toNumber(point.projected_price) }))
    .filter((p): p is { day: number; value: number } => p.value !== null)
  const forecastSeriesPoints = currentPrice !== null ? [{ day: 0, value: currentPrice }, ...trendPoints] : trendPoints
  const historicalPoints = sampleHistoricalPoints(historicalPrices, data.horizon)
  const historicalSeriesPoints = historicalPoints.map(({ day, value }) => ({ day, value }))

  // Real calendar date for every plotted day, so the chart's x-axis
  // reads "Sep 4" instead of an abstract "+3" offset -- built from the
  // same already-computed dates the historical/forecast points carry,
  // never a new date calculation.
  const dateLabels: Record<number, string> = {}
  historicalPoints.forEach((p) => {
    if (p.date) dateLabels[p.day] = p.date
  })
  data.price_trend.forEach((p) => {
    if (p.date) dateLabels[p.period] = p.date
  })

  const methodMarkers = showMethods ? buildMethodMarkers(data.technical_methods) : []

  const referenceLines: ForecastLineChartReferenceLine[] = showSma
    ? data.moving_averages
        .map((ma, i) => {
          const value = toNumber(ma.value)
          return value === null
            ? null
            : { label: `${ma.window}-day SMA`, value, color: i === 0 ? '#8a6d00' : '#7a3ab3' }
        })
        .filter((r): r is ForecastLineChartReferenceLine => r !== null)
    : []

  const series: ForecastLineChartSeries[] = []
  if (historicalSeriesPoints.length > 0) {
    series.push({ label: 'Historical', color: '#9ca3af', points: historicalSeriesPoints })
  }
  if (forecastSeriesPoints.length > 0) {
    series.push({ label: 'Forecast trend', color: '#2952a3', points: forecastSeriesPoints, dashed: true, area: true })
  }
  const hasChart = series.length > 0 || methodMarkers.length > 0

  const hasPriceTrend = data.price_trend.length > 0

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <div className="flex min-w-0 flex-1 flex-col gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">{data.label}</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-3 text-[10px] text-[var(--color-text-faint)] sm:flex">
              {historicalSeriesPoints.length > 0 && (
                <span className="flex items-center gap-1">
                  <span className="inline-block h-0.5 w-3 rounded-full" style={{ background: '#9ca3af' }} /> Historical
                </span>
              )}
              {forecastSeriesPoints.length > 0 && (
                <span className="flex items-center gap-1">
                  <span className="inline-block h-0.5 w-3 rounded-full" style={{ background: '#2952a3' }} /> Forecast trend
                </span>
              )}
            </div>
            <IndicatorsMenu showSma={showSma} onShowSmaChange={setShowSma} showMethods={showMethods} onShowMethodsChange={setShowMethods} />
          </div>
        </div>

        {hasChart ? (
          <ForecastLineChart series={series} markers={methodMarkers} referenceLines={referenceLines} dateLabels={dateLabels} />
        ) : (
          <p className="py-8 text-center text-xs text-[var(--color-text-faint)]">{data.price_trend_reason ?? 'No chartable data for this horizon.'}</p>
        )}

        <TrendStatusBanner signal={data.technical_signal} />

        {hasPriceTrend && <ForecastDataDrawer points={data.price_trend} />}
      </div>

      <div className="flex w-full flex-col gap-4 lg:w-72 lg:shrink-0">
        <ForecastSummaryPanel data={data} currentPrice={currentPrice} />
        <TechnicalSignalsStrip data={data} />
      </div>
    </div>
  )
}

export function ForecastSection({
  forecast,
  market,
}: {
  forecast: ReportForecastSection | null
  market?: ReportMarketSection | null
}) {
  const [horizon, setHorizon] = useState<ForecastHorizonKey>('daily')

  if (!forecast || !forecast.available) {
    return null
  }

  const hasFinancials = forecast.financial_metrics.length > 0
  const hasScenarios = forecast.valuation_scenarios.length > 0
  const activeHorizonForecast = forecast.horizons ? forecast.horizons[horizon] : null
  const hasHorizonContent = activeHorizonForecast
    ? activeHorizonForecast.price_trend.length > 0 || activeHorizonForecast.technical_methods.length > 0
    : false

  if (!hasFinancials && !hasScenarios && !hasHorizonContent) {
    return null
  }

  // The forecast pipeline's own quote (`forecast.current_price`) is
  // fetched independently of `report.market` and can be excluded by
  // stricter freshness gating (a stale quote is usable for display but
  // not for valuation) even when the market snapshot has a real price --
  // falling back to it means the Forecast tab still shows a current
  // price whenever one exists anywhere in the report, not just when the
  // forecast stage's own attempt succeeded.
  const usingMarketFallback = !forecast.current_price && !!market?.current_price
  const effectiveFormattedCurrentPrice = forecast.formatted_current_price ?? market?.formatted_current_price ?? null
  const currentPrice = toNumber(forecast.current_price) ?? toNumber(market?.current_price ?? null)

  return (
    <section aria-labelledby="forecast-heading" className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="forecast-heading" className="section-heading">
            Price Trend &amp; Forecast
          </h2>
          <p className="mt-1 text-xs text-[var(--color-text-faint)]">
            Deterministic extrapolation of historical data — not a recommendation, and never a single asserted price
            target.
          </p>
        </div>
        {effectiveFormattedCurrentPrice ? (
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">Current</div>
            <div className="font-mono-nums text-2xl font-semibold text-[var(--color-text)]">{effectiveFormattedCurrentPrice}</div>
            {usingMarketFallback && market?.freshness && market.freshness !== 'live' && (
              <div className="text-[10px] text-[var(--color-text-faint)]">({market.freshness})</div>
            )}
          </div>
        ) : (
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">Current</div>
            <div className="text-xs text-[var(--color-text-faint)]">Price unavailable</div>
          </div>
        )}
      </div>

      {hasFinancials && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
            Financial Projections{forecast.projection_years ? ` (${forecast.projection_years}-year)` : ''}
          </h3>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {forecast.financial_metrics.map((metric) => (
              <ForecastMetricCard key={metric.name} metric={metric} />
            ))}
          </div>
        </div>
      )}

      {hasScenarios && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
            Valuation Scenarios (DCF)
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {forecast.valuation_scenarios.map((scenario) => (
              <ValuationScenarioRow key={scenario.scenario} scenario={scenario} />
            ))}
          </div>
        </div>
      )}

      {forecast.horizons && (
        <div>
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
              Price Trend &amp; Technical Forecast
            </h3>
            <HorizonTabs active={horizon} onSelect={setHorizon} />
          </div>
          <HorizonForecastPanel
            data={forecast.horizons[horizon]}
            currentPrice={currentPrice}
            historicalPrices={forecast.historical_prices}
          />
          {(forecast.price_trend_disclaimer || forecast.technical_disclaimer) && (
            <p className="mt-3 text-xs text-[var(--color-text-faint)]">
              {forecast.price_trend_disclaimer ?? forecast.technical_disclaimer}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
