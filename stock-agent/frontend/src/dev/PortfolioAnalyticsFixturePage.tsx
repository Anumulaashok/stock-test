import type { ReactNode } from 'react'
import { ContributorsDetractors } from '../features/portfolio/ContributorsDetractors'
import { PositionSizeCalculator } from '../features/portfolio/PositionSizeCalculator'
import type { HoldingWithMarketData } from '../types/backend'

// Dev-only gallery; the calculator's "Look up price" button still hits the real API if clicked.

function holding(overrides: Partial<HoldingWithMarketData> = {}): HoldingWithMarketData {
  return {
    id: 'h1', ticker: 'ACME', quantity: '10', average_cost: '100', added_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    current_price: '120', price_status: 'live', market_value: '1200', unrealized_gain: '200', unrealized_gain_percent: '20',
    ...overrides,
  }
}

const MIXED_HOLDINGS: HoldingWithMarketData[] = [
  holding({ id: 'h1', ticker: 'WINNER', unrealized_gain_percent: '35', unrealized_gain: '350' }),
  holding({ id: 'h2', ticker: 'GAINER', unrealized_gain_percent: '8', unrealized_gain: '80' }),
  holding({ id: 'h3', ticker: 'LOSER', unrealized_gain_percent: '-15', unrealized_gain: '-150' }),
  holding({ id: 'h4', ticker: 'BIGLOSS', unrealized_gain_percent: '-40', unrealized_gain: '-400' }),
  holding({ id: 'h5', ticker: 'FLAT', unrealized_gain_percent: '0', unrealized_gain: '0' }),
  holding({ id: 'h6', ticker: 'NOPRICE', unrealized_gain_percent: null, unrealized_gain: null, current_price: null, price_status: 'unavailable', market_value: null }),
]

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2 border-b border-[var(--color-border)] pb-8 last:border-0">
      <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--color-text-muted)]">{title}</h2>
      {children}
    </section>
  )
}

export function PortfolioAnalyticsFixturePage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10">
      <div>
        <h1 className="text-lg font-bold">Portfolio Analytics Fixture Gallery (dev only)</h1>
        <p className="support-text text-xs">Contributors/detractors + position-size calculator. Not reachable in production.</p>
      </div>

      <Section title="Contributors/detractors -- mixed gains, losses, flat, and a no-price holding">
        <ContributorsDetractors holdings={MIXED_HOLDINGS} />
      </Section>

      <Section title="Contributors/detractors -- all holdings flat or unpriced (renders nothing)">
        <ContributorsDetractors holdings={[holding({ unrealized_gain_percent: '0' }), holding({ id: 'h2', ticker: 'B', unrealized_gain_percent: null })]} />
        <p className="support-text mt-2 text-xs">(Nothing above this line -- the component returns null when there's nothing to show.)</p>
      </Section>

      <Section title="Position size calculator">
        <PositionSizeCalculator />
      </Section>
    </main>
  )
}
