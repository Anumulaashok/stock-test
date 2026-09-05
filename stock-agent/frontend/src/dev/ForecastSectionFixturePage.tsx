import { ForecastSection } from '../components/ForecastSection'
import type { ReportForecastSection, ReportHorizonForecast } from '../types/backend'

/**
 * Dev-only fixture gallery for the Wave 3 deterministic-forecast method
 * cards + "Not backtested" badge, no network calls. Registered only in
 * dev (`main.tsx`, guarded by `import.meta.env.DEV`) and lazy-loaded.
 */

function horizon(overrides: Partial<ReportHorizonForecast> = {}): ReportHorizonForecast {
  return {
    horizon: 'daily',
    label: '30 Trading Days',
    price_trend: [
      { period: 1, day_offset: 1, date: '2026-08-28', projected_price: '101', formatted_projected_price: '$101.00' },
      { period: 5, day_offset: 5, date: '2026-09-02', projected_price: '103', formatted_projected_price: '$103.00' },
    ],
    price_trend_status: 'calculated',
    price_trend_reason: null,
    moving_averages: [
      { window: 50, value: '95', status: 'calculated', reason: null, formatted_value: '$95.00' },
      { window: 200, value: '90', status: 'calculated', reason: null, formatted_value: '$90.00' },
    ],
    crossover: { short_window: 50, long_window: 200, signal: 'golden_cross', status: 'calculated', reason: null },
    technical_methods: [
      { method: 'linear_regression', description: 'Ordinary least squares regression over recent closing prices.', projected_price: '103', projection_days: 5, horizon: 'daily', horizon_period: 30, projected_date: '2026-09-02', status: 'calculated', reason: null, formatted_projected_price: '$103.00' },
      { method: 'sma_50', description: '50-day simple moving average, a mean-reversion reference.', projected_price: '95', projection_days: 5, horizon: 'daily', horizon_period: 30, projected_date: '2026-09-02', status: 'calculated', reason: null, formatted_projected_price: '$95.00' },
      { method: 'sma_200', description: '200-day simple moving average, a mean-reversion reference.', projected_price: '90', projection_days: 5, horizon: 'daily', horizon_period: 30, projected_date: '2026-09-02', status: 'calculated', reason: null, formatted_projected_price: '$90.00' },
      { method: 'sma_crossover_momentum', description: 'Momentum drift from the 50/200-day spread.', projected_price: null, projection_days: 5, horizon: 'daily', horizon_period: 30, projected_date: null, status: 'unavailable', reason: 'current price is unavailable', formatted_projected_price: null },
    ],
    technical_signal: { label: 'bullish', color: 'green', reason: 'Golden cross with price confirming.' },
    ...overrides,
  }
}

const FORECAST: ReportForecastSection = {
  source: 'forecast',
  available: true,
  projection_years: 2,
  financial_metrics: [],
  valuation_scenarios: [],
  price_trend: [],
  price_trend_status: 'calculated',
  price_trend_reason: null,
  price_trend_disclaimer: 'Naive statistical extrapolation of recent closing prices using linear regression.',
  moving_averages: [
    { window: 50, value: '95', status: 'calculated', reason: null, formatted_value: '$95.00' },
    { window: 200, value: '90', status: 'calculated', reason: null, formatted_value: '$90.00' },
  ],
  crossover: { short_window: 50, long_window: 200, signal: 'golden_cross', status: 'calculated', reason: null },
  technical_methods: [],
  technical_disclaimer: 'Technical indicators computed from recent closing prices using well-known heuristic formulas.',
  technical_signal: { label: 'bullish', color: 'green', reason: 'Golden cross with price confirming.' },
  current_price: '99',
  formatted_current_price: '$99.00',
  horizons: { daily: horizon(), weekly: horizon({ horizon: 'weekly' }), monthly: horizon({ horizon: 'monthly' }) },
  historical_prices: [
    { date: '2026-08-20', close: '92', formatted_close: '$92.00' },
    { date: '2026-08-25', close: '96', formatted_close: '$96.00' },
    { date: '2026-08-27', close: '99', formatted_close: '$99.00' },
  ],
}

export function ForecastSectionFixturePage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10">
      <div>
        <h1 className="text-lg font-bold">Deterministic Forecast Fixture Gallery (dev only)</h1>
        <p className="support-text text-xs">
          Wave 3: the 4-method card row (one unavailable) + the permanent "Not backtested" badge, no network calls.
          Not reachable in production.
        </p>
      </div>
      <div className="surface-card p-4">
        <ForecastSection forecast={FORECAST} />
      </div>
    </main>
  )
}
