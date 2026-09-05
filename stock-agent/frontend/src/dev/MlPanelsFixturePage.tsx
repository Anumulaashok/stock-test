import { HorizonPanel } from '../components/stock/MlAccuracyPanel'
import { NewsImpactPanel } from '../components/stock/NewsImpactPanel'
import { AnalogPanel } from '../components/stock/AnalogPanel'
import { DetailsPanel, HorizonChip, resolvedPredictionMarkers } from '../components/stock/MlForecastPanel'
import { PriceChart } from '../components/PriceChart'
import type {
  MlAccuracyHorizonStats,
  MlForecastHistoryResponse,
  MlForecastPrediction,
  MlHorizonForecast,
  NewsImpactSection,
  AnalogSummary,
} from '../types/mlForecast'

function horizonForecast(overrides: Partial<MlHorizonForecast> = {}): MlHorizonForecast {
  return {
    horizon: '14D',
    target_date: '2026-08-15',
    current_price: 100,
    expected_return: 0.02,
    expected_price: 102,
    quantiles: { p10: 98, p25: 100, p50: 102, p75: 104, p90: 106 },
    probability_positive: 0.6,
    forecast_quality: 'HIGH',
    quality_score: 0.8,
    quality_reasons: [],
    model_agreement: 0.7,
    model_outputs: [
      { model_name: 'random_forest', point_return: 0.02, weight: 0.6 },
      { model_name: 'gradient_boosting_quantile', point_return: 0.03, weight: 0.4 },
    ],
    drivers: { positive_drivers: ['Momentum is positive'], negative_drivers: ['Valuation is stretched'] },
    analog: { sample_size: 0, is_reliable: false, positive_rate: null, negative_rate: null, mean_return: null, median_return: null, quantiles: null },
    historical_accuracy: { sample_size: 20, mae: 0.02, rmse: 0.03, directional_accuracy: 0.62, brier_score: 0.2, interval_coverage_80: 0.78 },
    ...overrides,
  }
}

const noop = () => {}

/**
 * Dev-only fixture gallery -- every ML-panel state rendered side by side
 * against fabricated response objects, with zero network calls. This is
 * the deliberate alternative to eyeballing against a real research run:
 * one real ticker gives you one state, and the states that most need
 * eyes (empty, below-calibration-n, degraded/unreliable) are exactly the
 * ones a live run is least likely to be sitting in when you happen to
 * look. Registered only in dev (`main.tsx`, guarded by `import.meta.env.DEV`)
 * and lazy-loaded, so none of this reaches the production bundle.
 *
 * Intentionally a permanent asset, not scaffolding -- every panel added
 * in Waves 2-5 should get a section here rather than relying on a live
 * backend to happen to be in the state that needs checking.
 */

function prediction(overrides: Partial<MlForecastPrediction> = {}): MlForecastPrediction {
  return {
    prediction_timestamp: '2026-08-01T09:00:00+00:00',
    horizon: '14D',
    predicted_return: 0.02,
    predicted_price: 102,
    target_date: '2026-08-15',
    actual_return: 0.03,
    actual_price: 103,
    direction_correct: true,
    forecast_quality: 'HIGH',
    model_version: 'v1',
    ...overrides,
  }
}

function history(predictions: MlForecastPrediction[]): MlForecastHistoryResponse {
  return { ticker: 'FIXTURE', predictions }
}

const POPULATED_STATS: MlAccuracyHorizonStats = {
  sample_size: 23,
  mae: 0.015,
  rmse: 0.021,
  directional_accuracy: 0.65,
  brier_score: 0.18,
  interval_coverage_80: 0.78,
}

const EMPTY_STATS: MlAccuracyHorizonStats = {
  sample_size: 0,
  mae: null,
  rmse: null,
  directional_accuracy: null,
  brier_score: null,
  interval_coverage_80: null,
  note: 'No walk-forward evaluation recorded yet',
}

function resolvedPrediction(i: number, correct: boolean): MlForecastPrediction {
  const predicted = 0.01 * (i + 1) * (i % 3 === 0 ? -1 : 1)
  const actual = correct ? predicted + 0.002 * (i % 2 === 0 ? 1 : -1) : -predicted - 0.002
  return prediction({
    target_date: `2026-0${(i % 9) + 1}-15`,
    predicted_return: predicted,
    actual_return: actual,
    direction_correct: correct,
  })
}

// Accuracy variants ----------------------------------------------------

const ACCURACY_POPULATED = history(Array.from({ length: 15 }, (_, i) => resolvedPrediction(i, i % 4 !== 0)))

const ACCURACY_N3 = history([
  resolvedPrediction(0, true),
  resolvedPrediction(1, false),
  resolvedPrediction(2, true),
])

const ACCURACY_EMPTY = history([])

// Scatter-focused variants (via HorizonPanel, so counts/labels show too) ----

const SCATTER_ALL_CORRECT = history(Array.from({ length: 12 }, (_, i) => resolvedPrediction(i, true)))

const SCATTER_MIXED = history(
  Array.from({ length: 16 }, (_, i) => resolvedPrediction(i, i % 3 !== 0)).concat([
    prediction({ target_date: '2026-09-01', predicted_return: 0.01, actual_return: 0.005, direction_correct: null }),
  ]),
)

const SCATTER_MOSTLY_PENDING = history([
  resolvedPrediction(0, true),
  resolvedPrediction(1, false),
  ...Array.from({ length: 10 }, (_, i) =>
    prediction({
      target_date: `2026-10-${String(i + 1).padStart(2, '0')}`,
      predicted_return: 0.01 * (i + 1),
      actual_return: null,
      actual_price: null,
      direction_correct: null,
    }),
  ),
])

// News-impact variants ---------------------------------------------------

const NEWS_POPULATED: NewsImpactSection = {
  data_available: true,
  note: null,
  recent_events: [
    {
      headline: 'Company beats consensus estimates on Q2 earnings',
      published_at: '2026-08-20T07:30:00+00:00',
      event_type: 'earnings',
      sentiment: 'POSITIVE',
      market_timing: 'pre_market',
      url: null,
    },
    {
      headline: 'Regulator opens inquiry into pricing practices',
      published_at: '2026-08-18T13:00:00+00:00',
      event_type: 'regulatory',
      sentiment: 'NEGATIVE',
      market_timing: 'intraday',
      url: null,
    },
    {
      headline: 'CEO announces unscheduled leadership transition',
      published_at: '2026-08-10T09:15:00+00:00',
      event_type: 'management_change',
      sentiment: 'NEUTRAL',
      market_timing: 'pre_market',
      url: null,
    },
  ],
  historical_statistics: [
    {
      event_type: 'earnings',
      sample_size: 23,
      is_reliable: true,
      median_return_5d: 0.021,
      median_return_14d: 0.034,
      positive_rate_5d: 0.65,
      positive_rate_14d: 0.7,
    },
    {
      event_type: 'regulatory',
      sample_size: 6,
      is_reliable: false,
      median_return_5d: -0.018,
      median_return_14d: -0.011,
      positive_rate_5d: 0.33,
      positive_rate_14d: 0.4,
    },
    // Deliberately no entry for "management_change" -- exercises a
    // recent event whose type has no matching historical statistic yet.
  ],
}

const NEWS_UNAVAILABLE: NewsImpactSection = {
  data_available: false,
  note: 'No news provider is configured for this deployment (NEWSDATA_API_KEY / NEWSAPI_API_KEY unset).',
  recent_events: [],
  historical_statistics: [],
}

// Analog variants ----------------------------------------------------------

const ANALOG_RELIABLE: AnalogSummary = {
  sample_size: 31,
  is_reliable: true,
  positive_rate: 0.58,
  negative_rate: 0.42,
  mean_return: 0.086,
  median_return: 0.012,
  quantiles: { p10: -0.09, p25: -0.02, p50: 0.012, p75: 0.05, p90: 0.31 },
}

const ANALOG_UNRELIABLE: AnalogSummary = {
  sample_size: 4,
  is_reliable: false,
  positive_rate: 0.75,
  negative_rate: 0.25,
  mean_return: 0.11,
  median_return: 0.008,
  quantiles: { p10: -0.03, p25: 0.0, p50: 0.008, p75: 0.04, p90: 0.42 },
}

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2 border-b border-[var(--color-border)] pb-8 last:border-0">
      <div>
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--color-text-muted)]">{title}</h2>
        {note && <p className="support-text text-xs">{note}</p>}
      </div>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">{children}</div>
    </section>
  )
}

export function MlPanelsFixturePage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10">
      <div>
        <h1 className="text-lg font-bold">ML Panel Fixture Gallery (dev only)</h1>
        <p className="support-text text-xs">
          Every ML-panel state rendered against fabricated responses, no network calls. Not reachable in production.
        </p>
      </div>

      <Section title="Accuracy -- populated (n=15, quadrant shading on)">
        <HorizonPanel horizon="14D" history={ACCURACY_POPULATED} accuracyStats={POPULATED_STATS} />
      </Section>

      <Section title="Accuracy -- n=3 resolved (shading suppressed)">
        <HorizonPanel horizon="14D" history={ACCURACY_N3} accuracyStats={POPULATED_STATS} />
      </Section>

      <Section title="Accuracy -- sample_size: 0 (fresh ticker, nothing resolved)">
        <HorizonPanel horizon="14D" history={ACCURACY_EMPTY} accuracyStats={EMPTY_STATS} />
      </Section>

      <Section title="Scatter -- all correct (n=12)">
        <HorizonPanel horizon="1M" history={SCATTER_ALL_CORRECT} accuracyStats={POPULATED_STATS} />
      </Section>

      <Section title="Scatter -- mixed correct/incorrect/unclassified (n=17)">
        <HorizonPanel horizon="3M" history={SCATTER_MIXED} accuracyStats={POPULATED_STATS} />
      </Section>

      <Section title="Scatter -- mostly pending (2 resolved, 10 pending)">
        <HorizonPanel horizon="1Y" history={SCATTER_MOSTLY_PENDING} accuracyStats={EMPTY_STATS} />
      </Section>

      <Section title="News impact -- populated, one recent event type with no historical_statistics match">
        <NewsImpactPanel newsImpact={NEWS_POPULATED} />
      </Section>

      <Section title="News impact -- data_available: false">
        <NewsImpactPanel newsImpact={NEWS_UNAVAILABLE} />
      </Section>

      <Section title="Analogs -- reliable, mean/median diverging sharply (skewed distribution)">
        <AnalogPanel analog={ANALOG_RELIABLE} horizonLabel="14D" />
      </Section>

      <Section title="Analogs -- unreliable (n=4), mean/median diverging sharply">
        <AnalogPanel analog={ANALOG_UNRELIABLE} horizonLabel="1Y" />
      </Section>

      <Section title="ML section (Wave 3) -- HIGH quality chip, weights, 80% interval coverage">
        <div className="flex flex-col gap-3">
          <HorizonChip forecast={horizonForecast()} active onSelect={noop} />
          <DetailsPanel forecast={horizonForecast()} />
        </div>
      </Section>

      <Section title="ML section (Wave 3) -- LOW quality chip, one model at weight 0">
        <div className="flex flex-col gap-3">
          <HorizonChip
            forecast={horizonForecast({
              forecast_quality: 'LOW',
              model_outputs: [
                { model_name: 'random_forest', point_return: 0.02, weight: 0 },
                { model_name: 'gradient_boosting_quantile', point_return: 0.01, weight: 1 },
              ],
            })}
            active
            onSelect={noop}
          />
          <DetailsPanel
            forecast={horizonForecast({
              forecast_quality: 'LOW',
              quality_reasons: ['Fewer than 60 days of price history for training.'],
              model_outputs: [
                { model_name: 'random_forest', point_return: 0.02, weight: 0 },
                { model_name: 'gradient_boosting_quantile', point_return: 0.01, weight: 1 },
              ],
            })}
          />
        </div>
      </Section>

      <Section title="ML section (Wave 3) -- naive-only fallback, must be visible on the collapsed chip">
        <HorizonChip
          forecast={horizonForecast({
            forecast_quality: 'LOW',
            model_outputs: [{ model_name: 'naive_zero_return', point_return: 0, weight: 1 }],
          })}
          active
          onSelect={noop}
        />
      </Section>

      <Section title="ML section (Wave 3) -- 80% interval coverage not yet available (no walk-forward evaluation)">
        <DetailsPanel forecast={horizonForecast({ historical_accuracy: { sample_size: 0, mae: null, rmse: null, directional_accuracy: null, brier_score: null, interval_coverage_80: null } })} />
      </Section>

      <Section title="Price chart -- resolved-prediction overlay (Wave 2, amber markers)">
        <PriceChart
          historical={[
            { date: '2026-07-20', value: 92 },
            { date: '2026-07-27', value: 94 },
            { date: '2026-08-03', value: 91 },
            { date: '2026-08-10', value: 96 },
            { date: '2026-08-14', value: 100 },
          ]}
          predicted={[
            { date: '2026-08-14', value: 100 },
            { date: '2026-08-28', value: 104 },
          ]}
          band={[{ date: '2026-08-28', low: 99, high: 109 }]}
          markers={resolvedPredictionMarkers([
            {
              prediction_timestamp: '2026-07-13T09:00:00+00:00',
              horizon: '14D',
              predicted_return: 0.02,
              predicted_price: 93.5,
              target_date: '2026-07-27',
              actual_return: 0.015,
              actual_price: 94,
              direction_correct: true,
              forecast_quality: 'HIGH',
              model_version: 'v1',
            },
            {
              prediction_timestamp: '2026-07-27T09:00:00+00:00',
              horizon: '14D',
              predicted_return: -0.01,
              predicted_price: 93,
              target_date: '2026-08-10',
              actual_return: 0.02,
              actual_price: 96,
              direction_correct: false,
              forecast_quality: 'MEDIUM',
              model_version: 'v1',
            },
            {
              prediction_timestamp: '2026-08-10T09:00:00+00:00',
              horizon: '14D',
              predicted_return: 0.01,
              predicted_price: 97,
              target_date: '2026-08-28',
              actual_return: null,
              actual_price: null,
              direction_correct: null,
              forecast_quality: 'HIGH',
              model_version: 'v1',
            },
          ])}
          ariaLabel="AI forecast price chart"
        />
        <p className="support-text mt-1 text-xs">
          Two resolved predictions (amber dots at Jul 27 and Aug 10) plus one pending (correctly excluded -- no marker
          at Aug 28). Judge: are the amber dots distinguishable from the gray historical line and the blue predicted/
          band region at a glance?
        </p>
      </Section>
    </main>
  )
}
