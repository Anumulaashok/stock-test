import { useState } from 'react'
import type {
  ForecastHorizonKey,
  MetricStatus,
  ReportHistoricalPricePoint,
  ReportHorizonForecast,
  ReportMarketSection,
  ReportForecastSection,
  ReportTechnicalMethod,
} from '../types/backend'
import { formatDate, humanizeKey } from '../lib/format'
import {
  PriceChart,
  type ForecastChartPoint,
  type ForecastLineChartMarker,
  type PriceChartEdgeMarker,
} from './PriceChart'

const METHOD_COLORS = ['#2952a3', '#b5540a', '#3a6b35', '#8a6d00', '#7a3ab3']

const METHOD_LABEL: Record<string, string> = {
  linear_regression: 'Linear Regression',
  sma_50: '50-day SMA',
  sma_200: '200-day SMA',
  sma_crossover_momentum: 'Crossover Momentum',
}

const HORIZON_TABS: { key: ForecastHorizonKey; label: string }[] = [
  { key: 'daily', label: 'Daily' },
  { key: 'weekly', label: 'Weekly' },
  { key: 'monthly', label: 'Monthly' },
]

function toNumber(value: string | null): number | null {
  if (value === null) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/** Every already-observed closing price, chronologically -- the full
 * history, never sampled or capped, so the chart shows all old data
 * alongside the prediction. Pure and presentation-only: it never
 * fabricates a value, only reshapes what the backend already computed.
 * Exported for unit testing. */
export function allHistoricalPrices(historicalPrices: ReportHistoricalPricePoint[]): ForecastChartPoint[] {
  return historicalPrices
    .map((p) => ({ date: p.date, value: toNumber(p.close) }))
    .filter((p): p is ForecastChartPoint => p.value !== null)
    .sort((a, b) => a.date.localeCompare(b.date))
}

/** The selected horizon's predicted points (already period-appropriate
 * -- daily/weekly/monthly-spaced, decided by the backend, never by this
 * component), bridged from "today" so the predicted line visually
 * connects to where the historical line ends. Exported for testing. */
export function predictedPrices(
  data: ReportHorizonForecast,
  currentPrice: number | null,
  todayDate: string | null,
): ForecastChartPoint[] {
  const trend = data.price_trend
    .map((point) => (point.date && toNumber(point.projected_price) !== null ? { date: point.date, value: toNumber(point.projected_price) as number } : null))
    .filter((p): p is ForecastChartPoint => p !== null)
  // A lone "today" bridge point with no actual future predictions isn't
  // a forecast line -- only prepend it when there's a real point to
  // draw a line to.
  if (trend.length === 0 || currentPrice === null || todayDate === null) return trend
  return [{ date: todayDate, value: currentPrice }, ...trend]
}

/** Builds one chart marker per non-trend technical method, positioned
 * at that method's own `projected_date` -- exported for unit testing. */
export function buildMethodMarkers(methods: ReportTechnicalMethod[]): ForecastLineChartMarker[] {
  const otherMethods = methods.filter((m) => m.method !== 'linear_regression' && m.status === 'calculated')
  return otherMethods
    .map((m, i) => {
      const value = toNumber(m.projected_price)
      return value === null || !m.projected_date
        ? null
        : { label: humanizeKey(m.method), date: m.projected_date, value, color: METHOD_COLORS[(i + 1) % METHOD_COLORS.length] }
    })
    .filter((m): m is ForecastLineChartMarker => m !== null)
}

export interface MethodCardData {
  method: string
  label: string
  description: string
  targetDate: string | null
  formattedProjectedPrice: string | null
  status: MetricStatus
  reason: string | null
}

/**
 * One card per deterministic method (Wave 3, I6): all four --
 * linear_regression, sma_50, sma_200, sma_crossover_momentum -- shown
 * side by side, parallel, never averaged into a single number.
 *
 * No % change or band is shown here (the master brief's card spec named
 * both) because neither is on `ReportTechnicalMethod` -- unlike
 * `ReportValuationMethod`, which already carries
 * `upside_downside_percent`, the technical-forecast methods have no
 * equivalent field, and no uncertainty range exists for a deterministic
 * point estimate at all. Computing either from `projected_price` and
 * `currentPrice` in TypeScript would be exactly the derived-statistic
 * violation I2 forbids. See BACKLOG.md, "% change field for deterministic
 * technical methods" and DECISIONS.md for this finding. Exported for
 * unit testing.
 */
export function buildMethodCards(methods: ReportTechnicalMethod[]): MethodCardData[] {
  return methods.map((m) => ({
    method: m.method,
    label: METHOD_LABEL[m.method] ?? humanizeKey(m.method),
    description: m.description,
    targetDate: m.projected_date,
    formattedProjectedPrice: m.formatted_projected_price,
    status: m.status,
    reason: m.reason,
  }))
}

function MethodCard({ card }: { card: MethodCardData }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <span className="text-xs font-semibold text-[var(--color-text-muted)]" title={card.description}>
        {card.label}
      </span>
      {card.status === 'calculated' ? (
        <>
          <span className="font-mono-nums text-lg font-semibold">{card.formattedProjectedPrice ?? '—'}</span>
          <span className="text-[10px] text-[var(--color-text-faint)]">{formatDate(card.targetDate) ?? '—'}</span>
        </>
      ) : (
        <span className="text-xs text-[var(--color-text-faint)]">{card.reason ?? 'Unavailable'}</span>
      )}
    </div>
  )
}

/** All four deterministic methods, side by side -- never blended into
 * one number (I6). Distinct visual unit from the chart above it, which
 * only overlays the "other methods" toggle's markers when enabled;
 * this row always shows every method regardless of that toggle. */
function MethodCardRow({ methods }: { methods: ReportTechnicalMethod[] }) {
  const cards = buildMethodCards(methods)
  if (cards.length === 0) return null
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {cards.map((card) => (
        <MethodCard key={card.method} card={card} />
      ))}
    </div>
  )
}

/** True when the backend's own reason for having nothing to chart
 * points at a fixable data gap (insufficient stored price history)
 * rather than a structural unavailability -- used only to decide
 * whether to add a pointer to the historical-import tool that fixes it. */
function isFixableWithHistoricalImport(reason: string | null): boolean {
  return reason !== null && /historical (price|closing price)/i.test(reason)
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

function HorizonChart({
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

  const historical = allHistoricalPrices(historicalPrices)
  // The bridge point (today's current price) is plotted on the same
  // date the historical line ends -- both series having a point there
  // is what visually connects them into one continuous line, without
  // guessing what "today" actually is from the forecast's own dates.
  const lastHistoricalDate = historical.length > 0 ? historical[historical.length - 1].date : null
  const predicted = predictedPrices(data, currentPrice, lastHistoricalDate)

  const methodMarkers = showMethods ? buildMethodMarkers(data.technical_methods) : []

  // Edge markers, not full-width reference lines: a full-width line at
  // today's SMA value would visually cross the historical price series
  // at points in history where no crossing actually occurred (the SMA
  // was elsewhere then) -- the exact anti-pattern named in DECISIONS.md
  // ("current-value-as-full-width-line"), fixed here per the same
  // authorization that fixed PriceChartSection's identical case.
  const edgeMarkers: PriceChartEdgeMarker[] = showSma
    ? data.moving_averages
        .map((ma, i) => {
          const value = toNumber(ma.value)
          return value === null
            ? null
            : { label: `${ma.window}-day SMA`, value, color: i === 0 ? '#8a6d00' : '#7a3ab3' }
        })
        .filter((r): r is PriceChartEdgeMarker => r !== null)
    : []

  const hasChart = historical.length > 0 || predicted.length > 0 || methodMarkers.length > 0
  // Distinct from `hasChart`: a chart showing only already-observed
  // historical prices, with no predicted point or marker at all, isn't
  // actually a forecast -- still worth showing (real data), but paired
  // with an honest note instead of implying a prediction exists.
  const hasPrediction = predicted.length > 0 || methodMarkers.length > 0

  const reason = data.price_trend_reason
  const showHistoricalImportHint = !hasPrediction && isFixableWithHistoricalImport(reason)

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">{data.label}</span>
        {hasChart && (
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-3 text-[10px] text-[var(--color-text-faint)] sm:flex">
              {historical.length > 0 && (
                <span className="flex items-center gap-1">
                  <span className="inline-block h-0.5 w-3 rounded-full" style={{ background: '#9ca3af' }} /> Historical
                </span>
              )}
              {predicted.length > 0 && (
                <span className="flex items-center gap-1">
                  <span className="inline-block h-0.5 w-3 rounded-full" style={{ background: '#2952a3' }} /> Predicted
                </span>
              )}
            </div>
            <IndicatorsMenu showSma={showSma} onShowSmaChange={setShowSma} showMethods={showMethods} onShowMethodsChange={setShowMethods} />
          </div>
        )}
      </div>

      {hasChart ? (
        <PriceChart
          historical={historical}
          predicted={predicted}
          markers={methodMarkers}
          edgeMarkers={edgeMarkers}
          ariaLabel="Forecast price chart"
        />
      ) : (
        <div className="flex flex-col items-center gap-1.5 py-10 text-center">
          <p className="text-xs text-[var(--color-text-faint)]">{reason ?? 'No chartable data for this horizon.'}</p>
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

      <MethodCardRow methods={data.technical_methods} />

      {hasChart && !hasPrediction && (
        <p className="text-xs text-[var(--color-text-faint)]">
          No prediction available for this horizon{reason ? ` — ${reason}` : ''}.
          {showHistoricalImportHint && (
            <>
              {' '}
              <a href="/settings/system" className="font-medium text-[var(--color-accent-strong)] hover:underline">
                Import price history
              </a>{' '}
              to unlock this.
            </>
          )}
        </p>
      )}
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

  if (!forecast || !forecast.available || !forecast.horizons) {
    return null
  }

  const activeHorizonForecast = forecast.horizons[horizon]
  const hasHorizonContent = activeHorizonForecast.price_trend.length > 0 || activeHorizonForecast.technical_methods.length > 0
  if (!hasHorizonContent) {
    return null
  }

  const effectiveFormattedCurrentPrice = forecast.formatted_current_price ?? market?.formatted_current_price ?? null
  const currentPrice = toNumber(forecast.current_price) ?? toNumber(market?.current_price ?? null)

  return (
    <section aria-labelledby="forecast-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 id="forecast-heading" className="section-heading">
            Price Trend &amp; Forecast
          </h2>
          <span
            className="rounded-full border border-[var(--color-border)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-text-faint)]"
            title="This deterministic forecast has never been evaluated against what actually happened -- unlike the AI Forecast section, which tracks its own accuracy."
          >
            Not backtested
          </span>
        </div>
        {effectiveFormattedCurrentPrice ? (
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">Current</div>
            <div className="font-mono-nums text-2xl font-semibold text-[var(--color-text)]">{effectiveFormattedCurrentPrice}</div>
          </div>
        ) : (
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">Current</div>
            <div className="text-xs text-[var(--color-text-faint)]">Price unavailable</div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-3">
        <HorizonTabs active={horizon} onSelect={setHorizon} />
      </div>

      <HorizonChart data={activeHorizonForecast} currentPrice={currentPrice} historicalPrices={forecast.historical_prices} />

      <p className="text-[11px] text-[var(--color-text-faint)]">
        {forecast.price_trend_disclaimer ?? forecast.technical_disclaimer ?? 'Deterministic extrapolation of historical data — not a recommendation.'}
      </p>
    </section>
  )
}
