import { useMemo, useState } from 'react'
import { fetchMlForecast, fetchMlForecastHistory } from '../../api/mlForecast'
import { useAsync } from '../../hooks/useAsync'
import { AsyncSection } from '../ui/AsyncSection'
import { formatCurrency, humanizeKey } from '../../lib/format'
import { allHistoricalPrices } from '../ForecastSection'
import {
  PriceChart,
  type ForecastChartPoint,
  type ForecastLineChartBandPoint,
  type ForecastLineChartMarker,
} from '../PriceChart'
import { NewsImpactPanel } from './NewsImpactPanel'
import { AnalogPanel } from './AnalogPanel'
import type { ReportHistoricalPricePoint } from '../../types/backend'
import type { MlForecastPrediction, MlForecastResult, MlHorizonForecast, MlHorizonKey } from '../../types/mlForecast'

const RESOLVED_PREDICTION_HISTORY_LIMIT = 200
const RESOLVED_PREDICTION_COLOR = '#c78a1f'

const HORIZON_ORDER: { key: MlHorizonKey; label: string }[] = [
  { key: '14D', label: '14D' },
  { key: '1M', label: '1M' },
  { key: '3M', label: '3M' },
  { key: '1Y', label: '1Y' },
]

const QUALITY_DOT: Record<string, string> = {
  HIGH: '#2f9e5c',
  MEDIUM: '#c78a1f',
  LOW: '#c94f3d',
}

const NAIVE_ONLY_MODEL = 'naive_zero_return'

/** True when every model behind this horizon's ensemble is the naive
 * fallback -- the "no trained artifacts" degradation path
 * (app/forecasting/ml/pipeline.py). This must be visible on the
 * collapsed chip, not only inside expanded details: a degraded state
 * that only shows up after clicking "Why?" is exactly the "quieter
 * footnote" I10 forbids. Exported for unit testing. */
export function isNaiveOnlyFallback(forecast: MlHorizonForecast): boolean {
  return forecast.model_outputs.length > 0 && forecast.model_outputs.every((m) => m.model_name === NAIVE_ONLY_MODEL)
}

function pct(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(decimals)}%`
}

/** Chart series built from the already-fetched forecast + historical
 * closes: the historical line stops "today," a dashed predicted line
 * bridges from today's price through each horizon's base estimate at
 * its actual target date, and a shaded band spans each horizon's
 * P10-P90 range. Pure presentation -- reshapes what the backend already
 * computed, fabricates nothing. */
function useChartSeries(result: MlForecastResult, historicalPoints: ReportHistoricalPricePoint[]) {
  return useMemo(() => {
    const historical = allHistoricalPrices(historicalPoints)
    const dataDate = result.data_date ?? historical[historical.length - 1]?.date ?? null

    const predicted: ForecastChartPoint[] = []
    const band: ForecastLineChartBandPoint[] = []
    if (dataDate !== null) {
      predicted.push({ date: dataDate, value: result.current_price })
      band.push({ date: dataDate, low: result.current_price, high: result.current_price })
    }
    for (const { key } of HORIZON_ORDER) {
      const forecast = result.horizons[key]
      if (!forecast) continue
      predicted.push({ date: forecast.target_date, value: forecast.expected_price })
      if (forecast.quantiles.p10 !== null && forecast.quantiles.p90 !== null) {
        band.push({ date: forecast.target_date, low: forecast.quantiles.p10, high: forecast.quantiles.p90 })
      }
    }

    return { historical, predicted, band }
  }, [result, historicalPoints])
}

/** One marker per already-resolved prediction (actual_return !== null),
 * placed at the model's predicted price on the date it resolved --
 * plotted against the real historical close already on the same chart,
 * so a viewer can see how close a past prediction actually was. Pending
 * predictions (actual_return === null) are excluded: there's nothing to
 * compare them against yet. This is Wave 1's deferred secondary view,
 * folded into the price chart rather than built as a third chart (per
 * the master brief). Exported for unit testing. */
export function resolvedPredictionMarkers(predictions: MlForecastPrediction[]): ForecastLineChartMarker[] {
  return predictions
    .filter((p) => p.actual_return !== null)
    .map((p) => ({ label: 'Past prediction', date: p.target_date, value: p.predicted_price, color: RESOLVED_PREDICTION_COLOR }))
}

/** Exported for the dev-only fixture route (`src/dev/MlPanelsFixturePage.tsx`)
 * -- renders directly against fabricated `MlHorizonForecast` data, zero
 * network calls, so quality/weight/naive-fallback states can be
 * eyeballed side by side. Not used by any other production call site. */
export function HorizonChip({ forecast, active, onSelect }: { forecast: MlHorizonForecast; active: boolean; onSelect: () => void }) {
  const label = HORIZON_ORDER.find((h) => h.key === forecast.horizon)?.label ?? forecast.horizon
  const naiveOnly = isNaiveOnlyFallback(forecast)
  const isLow = forecast.forecast_quality === 'LOW'
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex flex-col items-center gap-1 rounded-lg border px-3 py-2 text-left transition-colors ${
        naiveOnly
          ? 'border-[var(--color-status-negative)]/60 bg-[var(--color-status-negative)]/10'
          : active
            ? 'border-[var(--color-border-strong)] bg-[var(--color-surface-raised)]'
            : 'border-[var(--color-border)] bg-[var(--color-surface)]'
      }`}
    >
      <span className="flex items-center gap-1.5 text-xs font-semibold">
        <span
          aria-hidden
          className="inline-block h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: QUALITY_DOT[forecast.forecast_quality] ?? '#888' }}
        />
        {label}
        {isLow && (
          <span className="rounded-sm bg-[var(--color-status-negative)]/15 px-1 text-[9px] font-bold uppercase text-[var(--color-status-negative)]">
            Low
          </span>
        )}
      </span>
      <span className="text-sm font-semibold">{formatCurrency(forecast.expected_price)}</span>
      <span className="support-text text-xs">{pct(forecast.probability_positive)} up</span>
      {naiveOnly && (
        <span className="text-[9px] font-semibold uppercase tracking-wide text-[var(--color-status-negative)]">
          Naive fallback only
        </span>
      )}
    </button>
  )
}

/** Exported for the same dev-only fixture route as `HorizonChip`. */
export function DetailsPanel({ forecast }: { forecast: MlHorizonForecast }) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-sm">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <div className="support-text text-xs">Range (p10-p90)</div>
          <div>
            {formatCurrency(forecast.quantiles.p10)} – {formatCurrency(forecast.quantiles.p90)}
          </div>
        </div>
        <div>
          <div className="support-text text-xs">80% interval coverage</div>
          <div title="This band's own calibration: how often the real 80% interval actually contained the outcome, out of sample.">
            {forecast.historical_accuracy && forecast.historical_accuracy.sample_size > 0 && forecast.historical_accuracy.interval_coverage_80 !== null
              ? pct(forecast.historical_accuracy.interval_coverage_80)
              : 'Not yet available'}
          </div>
        </div>
        <div>
          <div className="support-text text-xs">Quality</div>
          <div>{forecast.forecast_quality}</div>
        </div>
        <div>
          <div className="support-text text-xs">Model agreement</div>
          <div>{pct(forecast.model_agreement)}</div>
        </div>
        <div>
          <div className="support-text text-xs">Out-of-sample accuracy</div>
          <div>
            {forecast.historical_accuracy && forecast.historical_accuracy.sample_size > 0
              ? pct(forecast.historical_accuracy.directional_accuracy)
              : 'Not yet available'}
          </div>
        </div>
      </div>

      <div>
        <div className="mb-1 support-text text-xs uppercase tracking-wide">Why</div>
        <ul className="flex flex-col gap-1">
          {forecast.drivers.positive_drivers.map((d) => (
            <li key={d}>+ {d}</li>
          ))}
          {forecast.drivers.negative_drivers.map((d) => (
            <li key={d}>− {d}</li>
          ))}
          {forecast.drivers.positive_drivers.length === 0 && forecast.drivers.negative_drivers.length === 0 && (
            <li className="support-text">No standout drivers identified.</li>
          )}
        </ul>
      </div>

      {forecast.quality_reasons.length > 0 && (
        <div>
          <div className="mb-1 support-text text-xs uppercase tracking-wide">Quality notes</div>
          <ul className="flex flex-col gap-1 support-text">
            {forecast.quality_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {forecast.model_outputs.length > 0 && (
        <div>
          <div className="mb-1 support-text text-xs uppercase tracking-wide">
            Per-model estimate <span className="normal-case">(weight = inverse walk-forward MAE)</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {forecast.model_outputs.map((m) => (
              <span
                key={m.model_name}
                className={`rounded border px-1.5 py-0.5 text-xs ${
                  m.weight === 0 ? 'border-[var(--color-status-negative)]/40 text-[var(--color-status-negative)]' : 'border-[var(--color-border)]'
                }`}
                title={m.weight === 0 ? 'No valid walk-forward result for this model -- contributes nothing to the ensemble.' : undefined}
              >
                {humanizeKey(m.model_name)}: {m.point_return >= 0 ? '+' : ''}
                {pct(m.point_return, 1)} · weight{' '}
                {m.weight === 0 ? '0 (no valid walk-forward result)' : pct(m.weight)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ForecastContent({
  ticker,
  result,
  historicalPoints,
}: {
  ticker: string
  result: MlForecastResult
  historicalPoints: ReportHistoricalPricePoint[]
}) {
  const { historical, predicted, band } = useChartSeries(result, historicalPoints)
  const [selected, setSelected] = useState<MlHorizonKey>('14D')
  const [showDetails, setShowDetails] = useState(false)
  const selectedForecast = result.horizons[selected]

  // Same GET .../history endpoint the accuracy panel already calls, for
  // the currently selected horizon -- a local DB read, not a metered
  // provider call (G9). Not embedded in `result` (MlForecastResult
  // carries no prediction history), so this is a genuinely new fetch,
  // not a redundant one (G5).
  const historyState = useAsync(() => fetchMlForecastHistory(ticker, selected, RESOLVED_PREDICTION_HISTORY_LIMIT), [
    ticker,
    selected,
  ])
  const resolvedMarkers =
    historyState.status === 'success' ? resolvedPredictionMarkers(historyState.data.predictions) : []

  return (
    <div className="flex flex-col gap-3">
      <PriceChart
        historical={historical}
        predicted={predicted}
        band={band}
        markers={resolvedMarkers}
        ariaLabel="AI forecast price chart"
      />
      {resolvedMarkers.length > 0 && (
        <p className="support-text text-xs">
          Amber markers show this model's past predicted price for {selected} forecasts that have since resolved --
          compare against the real price line above to see how close each one was.
        </p>
      )}

      <div className="grid grid-cols-4 gap-2">
        {HORIZON_ORDER.map(({ key }) => {
          const forecast = result.horizons[key]
          if (!forecast) return null
          return <HorizonChip key={key} forecast={forecast} active={key === selected} onSelect={() => setSelected(key)} />
        })}
      </div>

      {result.warnings.length > 0 && <p className="support-text text-xs">{result.warnings.join(' ')}</p>}

      <button
        type="button"
        onClick={() => setShowDetails((v) => !v)}
        className="self-start text-xs font-medium text-[var(--color-text-muted)] hover:underline"
      >
        {showDetails ? 'Hide details' : `Why ${selectedForecast?.horizon ?? ''}? (drivers, model breakdown)`}
      </button>

      {showDetails && selectedForecast && <DetailsPanel forecast={selectedForecast} />}

      <p className="support-text text-xs">Model estimate, not a guaranteed target -- regime: {humanizeKey(result.regime)}.</p>

      {selectedForecast && (
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <AnalogPanel analog={selectedForecast.analog} horizonLabel={selectedForecast.horizon} />
        </div>
      )}

      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <NewsImpactPanel newsImpact={result.news_impact} />
      </div>
    </div>
  )
}

/** New multi-horizon ML forecast panel (spec section 26) -- rendered
 * alongside, never in place of, the existing deterministic
 * `ForecastSection` (see `ForecastTab.tsx`), which stays the Technical
 * Baseline (spec section 27). Chart-first: the historical + projected
 * price line and quantile band are always visible; per-horizon
 * explanation/model-breakdown/news content is collapsed by default. */
export function MlForecastPanel({ ticker, historicalPrices }: { ticker: string; historicalPrices: ReportHistoricalPricePoint[] }) {
  const state = useAsync(() => fetchMlForecast(ticker), [ticker])

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-base font-semibold">AI Forecast</h3>
      <AsyncSection state={state} onRetry={state.reload} errorTitle="Could not load AI forecast">
        {(result) => <ForecastContent ticker={ticker} result={result} historicalPoints={historicalPrices} />}
      </AsyncSection>
    </div>
  )
}
