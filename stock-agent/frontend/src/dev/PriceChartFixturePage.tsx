import { PriceChartSection } from '../components/stock/PriceChartSection'
import type { ReportForecastSection, ReportHistoricalPricePoint } from '../types/backend'

/**
 * Dev-only fixture gallery for the Wave 2 shared price chart
 * (`PriceChartSection`/`PriceChart`) -- every crossover state, the
 * volume sub-chart on/off, and the no-history empty state, rendered
 * against fabricated data with zero network calls. Registered only in
 * dev (`main.tsx`, guarded by `import.meta.env.DEV`) and lazy-loaded.
 */

function pricePoint(date: string, close: number, volume: number | null): ReportHistoricalPricePoint {
  return {
    date,
    close: String(close),
    volume: volume === null ? null : String(volume),
    formatted_close: `$${close.toFixed(2)}`,
  }
}

const HISTORY_WITH_VOLUME: ReportHistoricalPricePoint[] = [
  pricePoint('2026-08-20', 92, 1100),
  pricePoint('2026-08-21', 94, 1300),
  pricePoint('2026-08-24', 96, 1250),
  pricePoint('2026-08-25', 98, 1400),
  pricePoint('2026-08-26', 99, 1500),
]

const HISTORY_NO_VOLUME: ReportHistoricalPricePoint[] = HISTORY_WITH_VOLUME.map((p) => ({ ...p, volume: null }))

function forecastFixture(overrides: Partial<ReportForecastSection> = {}): ReportForecastSection {
  return {
    source: 'forecast',
    available: true,
    projection_years: 2,
    financial_metrics: [],
    valuation_scenarios: [],
    price_trend: [],
    price_trend_status: null,
    price_trend_reason: null,
    price_trend_disclaimer: null,
    moving_averages: [
      { window: 50, value: '95', status: 'calculated', reason: null, formatted_value: '$95.00' },
      { window: 200, value: '90', status: 'calculated', reason: null, formatted_value: '$90.00' },
    ],
    crossover: { short_window: 50, long_window: 200, signal: 'golden_cross', status: 'calculated', reason: null },
    technical_methods: [],
    technical_disclaimer: null,
    technical_signal: null,
    current_price: '99',
    formatted_current_price: '$99.00',
    horizons: null,
    historical_prices: HISTORY_WITH_VOLUME,
    ...overrides,
  }
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2 border-b border-[var(--color-border)] pb-8 last:border-0">
      <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--color-text-muted)]">{title}</h2>
      <div className="surface-card p-4">{children}</div>
    </section>
  )
}

export function PriceChartFixturePage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10">
      <div>
        <h1 className="text-lg font-bold">Price Chart Fixture Gallery (dev only)</h1>
        <p className="support-text text-xs">
          Every crossover state, volume on/off, and the no-history empty state, no network calls. Not reachable in
          production.
        </p>
      </div>

      <Section title="Golden cross, with volume sub-chart">
        <PriceChartSection forecast={forecastFixture()} />
      </Section>

      <Section title="Death cross">
        <PriceChartSection
          forecast={forecastFixture({
            crossover: { short_window: 50, long_window: 200, signal: 'death_cross', status: 'calculated', reason: 'Price fell below both averages.' },
          })}
        />
      </Section>

      <Section title="Neutral crossover">
        <PriceChartSection
          forecast={forecastFixture({
            crossover: { short_window: 50, long_window: 200, signal: 'neutral', status: 'calculated', reason: null },
          })}
        />
      </Section>

      <Section title="No crossover value (badge renders nothing)">
        <PriceChartSection forecast={forecastFixture({ crossover: null })} />
      </Section>

      <Section title="No volume on any historical point (no sub-chart)">
        <PriceChartSection forecast={forecastFixture({ historical_prices: HISTORY_NO_VOLUME })} />
      </Section>

      <Section title="No moving averages (no SMA reference lines, no caveat text)">
        <PriceChartSection forecast={forecastFixture({ moving_averages: [] })} />
      </Section>

      <Section title="No price history -- honest empty state with import link">
        <PriceChartSection forecast={forecastFixture({ historical_prices: [] })} />
      </Section>
    </main>
  )
}
