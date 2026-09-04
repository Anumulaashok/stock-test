import { useMemo, useState } from 'react'
import { fetchMlForecastAccuracy, fetchMlForecastHistory } from '../../api/mlForecast'
import { useAsync } from '../../hooks/useAsync'
import { AsyncSection } from '../ui/AsyncSection'
import { EmptyState } from '../SectionHeader'
import { AccuracyScatterChart, MIN_N_FOR_QUADRANT_SHADING } from './AccuracyScatterChart'
import type {
  MlAccuracyHorizonStats,
  MlForecastAccuracyResponse,
  MlForecastHistoryResponse,
  MlHorizonKey,
} from '../../types/mlForecast'

const HORIZON_ORDER: MlHorizonKey[] = ['14D', '1M', '3M', '1Y']
const HISTORY_FETCH_LIMIT = 200

function pct(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(decimals)}%`
}

function num(value: number | null | undefined, decimals = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toFixed(decimals)
}

function HorizonTab({ label, active, onSelect }: { label: string; active: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={active ? 'true' : undefined}
      className={`rounded-md border px-3 py-1.5 text-xs font-semibold transition-colors ${
        active
          ? 'border-[var(--color-border-strong)] bg-[var(--color-surface-raised)] text-[var(--color-text)]'
          : 'border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-muted)]'
      }`}
    >
      {label}
    </button>
  )
}

/** Sample size shown at equal visual weight to the statistic it backs,
 * per every accuracy figure in this panel -- an accuracy number without
 * its n next to it is not trustworthy on its own. */
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

function WalkForwardStats({ stats, horizonLabel }: { stats: MlAccuracyHorizonStats | undefined; horizonLabel: string }) {
  if (!stats || stats.sample_size === 0) {
    // The title states the horizon-scoped absence; the reason is
    // reserved for WHY or WHAT-NEXT, never a restatement of the same
    // fact -- the backend's own `note` for this case is literally "No
    // walk-forward evaluation recorded yet" (`app/api/ml_forecast.py`),
    // which would otherwise read as the title repeated verbatim right
    // below itself. Title and reason must never share that wording.
    return (
      <EmptyState
        title={`Not evaluated yet for ${horizonLabel}`}
        reason={
          stats?.note ??
          'This fills in once the model has been backtested against enough historical windows for this horizon. Not a failure -- just not run yet.'
        }
      />
    )
  }
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <StatWithN label="Directional accuracy" value={pct(stats.directional_accuracy)} sampleSize={stats.sample_size} />
      <StatWithN label="Mean absolute error" value={pct(stats.mae)} sampleSize={stats.sample_size} />
      <StatWithN label="RMSE" value={pct(stats.rmse)} sampleSize={stats.sample_size} />
      <StatWithN label="Brier score" value={num(stats.brier_score)} sampleSize={stats.sample_size} />
      <StatWithN
        label="80% interval coverage"
        value={stats.interval_coverage_80 === null ? '—' : pct(stats.interval_coverage_80)}
        sampleSize={stats.sample_size}
      />
    </div>
  )
}

/** Exported for the dev-only fixture route (`src/dev/MlPanelsFixturePage.tsx`)
 * -- it renders this directly against fabricated `history`/`accuracyStats`
 * so every state (empty, below-calibration-n, populated) can be eyeballed
 * side by side with zero network calls, never through `MlAccuracyPanel`'s
 * own fetch. Not used by any other production call site. */
export function HorizonPanel({
  horizon,
  history,
  accuracyStats,
}: {
  horizon: MlHorizonKey
  history: MlForecastHistoryResponse
  accuracyStats: MlAccuracyHorizonStats | undefined
}) {
  const resolved = useMemo(() => history.predictions.filter((p) => p.actual_return !== null), [history.predictions])
  const pending = useMemo(() => history.predictions.filter((p) => p.actual_return === null), [history.predictions])
  const truncated = history.predictions.length >= HISTORY_FETCH_LIMIT

  const scatterPoints = useMemo(
    () =>
      resolved.map((p) => ({
        targetDate: p.target_date,
        predictedReturn: p.predicted_return,
        // actual_return is guaranteed non-null here by the `resolved` filter above.
        actualReturn: p.actual_return as number,
        directionCorrect: p.direction_correct,
      })),
    [resolved],
  )
  const belowCalibrationMinimum = resolved.length > 0 && resolved.length < MIN_N_FOR_QUADRANT_SHADING

  return (
    <div className="flex flex-col gap-4">
      <p className="support-text text-xs">
        {resolved.length} resolved · {pending.length} pending
        {pending.length > 0 && ' (excluded from every accuracy figure below until their target date passes)'}
        {truncated && ` — showing the most recent ${HISTORY_FETCH_LIMIT} predictions for ${horizon}`}
      </p>

      <div>
        <div className="mb-1.5 support-text text-xs uppercase tracking-wide">Predicted vs. actual return</div>
        {resolved.length === 0 ? (
          <EmptyState
            title="No resolved predictions yet"
            reason={
              pending.length > 0
                ? `${pending.length} prediction${pending.length === 1 ? '' : 's'} for this horizon ${pending.length === 1 ? 'is' : 'are'} still pending -- this chart fills in as each one's target date passes.`
                : 'No predictions have been made for this horizon yet. One is recorded automatically each time this ticker is forecast.'
            }
          />
        ) : (
          <>
            <AccuracyScatterChart points={scatterPoints} />
            {belowCalibrationMinimum ? (
              <p className="support-text mt-1 text-xs">
                Only {resolved.length} resolved prediction{resolved.length === 1 ? '' : 's'} -- below {MIN_N_FOR_QUADRANT_SHADING},
                too few for a calibration read. Points are real; the quadrant shading that would normally group them is
                withheld until there are more.
              </p>
            ) : (
              <p className="support-text mt-1 text-xs">
                Shaded quadrants are illustrative (top-right/bottom-left = same-direction call). Each point's own color and
                shape reflect the model's own direction_correct classification, which is authoritative even where a point
                sits near the shading boundary.
              </p>
            )}
          </>
        )}
      </div>

      <div>
        <div className="mb-1.5 support-text text-xs uppercase tracking-wide">Walk-forward evaluation</div>
        <WalkForwardStats stats={accuracyStats} horizonLabel={horizon} />
      </div>
    </div>
  )
}

function HorizonHistorySection({
  ticker,
  horizon,
  accuracyStats,
}: {
  ticker: string
  horizon: MlHorizonKey
  accuracyStats: MlAccuracyHorizonStats | undefined
}) {
  const historyState = useAsync(() => fetchMlForecastHistory(ticker, horizon, HISTORY_FETCH_LIMIT), [ticker, horizon])
  return (
    <AsyncSection state={historyState} onRetry={historyState.reload} errorTitle="Could not load prediction history">
      {(history) => <HorizonPanel horizon={horizon} history={history} accuracyStats={accuracyStats} />}
    </AsyncSection>
  )
}

function AccuracyContent({ result, ticker }: { result: MlForecastAccuracyResponse; ticker: string }) {
  const [selected, setSelected] = useState<MlHorizonKey>('14D')

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1.5">
          {HORIZON_ORDER.map((key) => (
            <HorizonTab key={key} label={key} active={key === selected} onSelect={() => setSelected(key)} />
          ))}
        </div>
      </div>
      <HorizonHistorySection ticker={ticker} horizon={selected} accuracyStats={result.accuracy_by_horizon[selected]} />
      <p className="support-text text-xs">
        Tracks {ticker}'s own ML forecasting history -- not backtested against any other ticker, and not the same system as
        the Technical Baseline forecast, which is not backtested at all.
      </p>
    </div>
  )
}

/** Prediction-vs-actual calibration + walk-forward accuracy for the ML
 * forecast subsystem (`app.forecasting.ml`). Deliberately separate from
 * `MlForecastPanel` and from the deterministic `ForecastSection` -- this
 * is the one forecast surface in the app that has a real track record to
 * show, and it must never be visually merged with the ones that don't.
 *
 * History is fetched per-horizon (`GET .../history?horizon=...`), never
 * as one unfiltered call bucketed client-side -- the backend orders
 * newest-first and applies `limit` before any horizon grouping, so an
 * unfiltered fetch can silently starve a horizon that predicts less
 * often than the others. This is a calibration chart; a biased sample
 * here is actively misleading, not just imprecise. */
export function MlAccuracyPanel({ ticker }: { ticker: string }) {
  const accuracyState = useAsync(() => fetchMlForecastAccuracy(ticker), [ticker])

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-base font-semibold">Forecast Accuracy</h3>
      <AsyncSection state={accuracyState} onRetry={accuracyState.reload} errorTitle="Could not load forecast accuracy">
        {(result) => <AccuracyContent result={result} ticker={ticker} />}
      </AsyncSection>
    </div>
  )
}
