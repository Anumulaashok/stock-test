import { CompareTable } from '../features/compare/CompareTable'
import { buildFinancialMetricRows, buildRiskRows, buildSummaryRows, buildValuationRows } from '../features/compare/compareRows'
import type { InvestmentResearchReport } from '../types/backend'

/**
 * Dev-only fixture gallery for the Wave 5 Compare feature, no network
 * calls. Registered only in dev (`main.tsx`, guarded by
 * `import.meta.env.DEV`) and lazy-loaded.
 */

function report(overrides: Partial<InvestmentResearchReport> = {}): InvestmentResearchReport {
  return {
    company: { name: 'Acme Corp', ticker: 'ACME', currency: null },
    status: 'calculated',
    market: { source: 'yfinance', current_price: '2610.5', previous_close: '2600', change: '10.5', change_percent: '0.4', currency: 'INR', market_status: 'open', market_timestamp: null, freshness: 'live', market_cap: null, year_high: null, year_low: null, formatted_current_price: '₹2,610.50' },
    summary: { overall_score: '78', overall_status: 'calculated', score_band: 'good', signal: { label: 'strong', color: 'green', reason: 'r' }, investment_thesis: null, key_takeaways: [] },
    financials: {
      source: 'financial_analysis', periods_analyzed: ['FY2024'],
      profitability: [{ name: 'roe', value: '24', unit: '%', status: 'calculated', reason: null, source_periods: [], formatted_value: '24.0%' }],
      growth: [{ name: 'revenue_growth', value: '12', unit: '%', status: 'calculated', reason: null, source_periods: [], formatted_value: '12.0%' }],
      financial_health: [], cash_flow: [], other: [],
    },
    valuation: {
      source: 'valuation', current_share_price: '2610.5', formatted_current_share_price: '₹2,610.50',
      methods: [{ method: 'dcf', value_per_share: '3000', status: 'calculated', reason: null, upside_downside_percent: '15', upside_downside_status: 'calculated', assumptions: {}, formatted_value_per_share: '₹3,000.00', formatted_upside_downside: '+15.0%' }],
    },
    scoring: null,
    risk: { source: 'scoring', critical: [], high: [{ name: 'x', severity: 'high', status: 'calculated', value: null, threshold: null, reason: 'r' }], medium: [], low: [], informational: [] },
    forecast: null, research: null, analyst: null,
    evidence: { financial: [], valuation: [], risk: [], research: [] }, warnings: [],
    metadata: { report_version: '1.0', generated_at: '2026-01-01T00:00:00Z', pipeline_version: '1.0', duration_ms: 1 },
    ...overrides,
  }
}

const ACME = report()
const BETA = report({
  company: { name: 'Beta Ltd', ticker: 'BETA', currency: null },
  summary: { overall_score: '55', overall_status: 'calculated', score_band: 'fair', signal: null, investment_thesis: null, key_takeaways: [] },
  valuation: {
    source: 'valuation', current_share_price: '500', formatted_current_share_price: '₹500.00',
    methods: [{ method: 'dcf', value_per_share: '520', status: 'calculated', reason: null, upside_downside_percent: '4', upside_downside_status: 'calculated', assumptions: {}, formatted_value_per_share: '₹520.00', formatted_upside_downside: '+4.0%' }],
  },
  financials: { source: 'financial_analysis', periods_analyzed: [], profitability: [], growth: [], financial_health: [], cash_flow: [], other: [] },
})
const GAMMA_NEVER_RESEARCHED: InvestmentResearchReport | null = null

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2 border-b border-[var(--color-border)] pb-8 last:border-0">
      <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--color-text-muted)]">{title}</h2>
      {children}
    </section>
  )
}

export function CompareFixturePage() {
  const reports = [ACME, BETA, GAMMA_NEVER_RESEARCHED]
  const tickers = ['ACME', 'BETA', 'GAMMA']

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-8 px-4 py-10">
      <div>
        <h1 className="text-lg font-bold">Compare Fixture Gallery (dev only)</h1>
        <p className="support-text text-xs">
          3 tickers, one never researched -- best/worst highlighting, unavailable cells. No network calls.
        </p>
      </div>

      <Section title="Summary (best/worst on score only)">
        <CompareTable title="Summary" rows={buildSummaryRows(reports, tickers)} tickers={tickers} />
      </Section>

      <Section title="Valuation (best/worst on upside for the same method)">
        <CompareTable title="Valuation" rows={buildValuationRows(reports, tickers)} tickers={tickers} />
      </Section>

      <Section title="Financial metrics (no best/worst -- ambiguous directionality)">
        <CompareTable title="Financial metrics" rows={buildFinancialMetricRows(reports, tickers)} tickers={tickers} />
      </Section>

      <Section title="Risk (plain counts, no best/worst)">
        <CompareTable title="Risk" rows={buildRiskRows(reports, tickers)} tickers={tickers} />
      </Section>
    </main>
  )
}
