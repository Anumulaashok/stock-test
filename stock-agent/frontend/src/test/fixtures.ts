import type { CombinedAnalysisResult, InvestmentResearchReport, ResearchRunResult } from '../types/backend'

/** A representative report matching the backend's actual JSON shape
 * (Decimal fields as strings), used across component tests. */
export function buildReport(overrides: Partial<InvestmentResearchReport> = {}): InvestmentResearchReport {
  return {
    company: { name: 'Acme Corp', ticker: 'ACME', currency: null },
    status: 'calculated',
    market: {
      source: 'yfinance',
      current_price: '100',
      previous_close: '97.65',
      change: '2.35',
      change_percent: '2.41',
      currency: 'INR',
      market_status: 'open',
      market_timestamp: '2026-03-01T10:00:00+00:00',
      freshness: 'live',
      market_cap: '500000000000',
      year_high: '120',
      year_low: '80',
      formatted_current_price: '₹100.00',
    },
    summary: {
      overall_score: '78',
      overall_status: 'calculated',
      score_band: 'good',
      signal: { label: 'strong', color: 'green', reason: 'Overall score is good with no high-severity risk indicators.' },
      investment_thesis: 'Acme Corp shows strong profitability.',
      key_takeaways: ['ROE is a strength'],
    },
    financials: {
      source: 'financial_analysis',
      periods_analyzed: ['FY2023', 'FY2024'],
      profitability: [
        { name: 'roe', value: '24', unit: '%', status: 'calculated', reason: null, source_periods: ['FY2024'], formatted_value: '24.00%' },
      ],
      growth: [
        { name: 'fcf_growth', value: null, unit: '%', status: 'unavailable', reason: 'insufficient historical periods', source_periods: [], formatted_value: null },
      ],
      financial_health: [],
      cash_flow: [],
      other: [],
    },
    valuation: {
      source: 'valuation',
      current_share_price: '100',
      formatted_current_share_price: '$100.00',
      methods: [
        {
          method: 'dcf', value_per_share: '140', status: 'calculated', reason: null,
          upside_downside_percent: '40', upside_downside_status: 'calculated',
          assumptions: { discount_rate: '0.09' },
          formatted_value_per_share: '$140.00', formatted_upside_downside: '40.00%',
        },
        {
          method: 'pe', value_per_share: null, status: 'unavailable', reason: 'EPS is missing',
          upside_downside_percent: null, upside_downside_status: null,
          assumptions: {}, formatted_value_per_share: null, formatted_upside_downside: null,
        },
      ],
    },
    scoring: {
      source: 'scoring',
      overall_score: '78',
      overall_status: 'calculated',
      band: 'good',
      categories: [
        { category: 'profitability', score: '85', weight: '0.20', status: 'calculated', band: 'strong', reason: null, components: [] },
        { category: 'valuation', score: null, weight: '0.20', status: 'unavailable', band: null, reason: 'No valuation data was provided.', components: [] },
      ],
    },
    risk: {
      source: 'scoring',
      critical: [],
      high: [{ name: 'high_debt_to_equity', severity: 'high', status: 'calculated', value: '3', threshold: '2', reason: 'debt/equity is elevated' }],
      medium: [],
      low: [],
      informational: [{ name: 'negative_fcf', severity: null, status: 'calculated', value: '250', threshold: '0', reason: 'free cash flow is not negative' }],
    },
    forecast: {
      source: 'forecast',
      available: false,
      projection_years: null,
      financial_metrics: [],
      valuation_scenarios: [],
      price_trend: [],
      price_trend_status: null,
      price_trend_reason: null,
      price_trend_disclaimer: null,
      moving_averages: [],
      crossover: null,
      technical_methods: [],
      technical_disclaimer: null,
      technical_signal: null,
      current_price: null,
      formatted_current_price: null,
      horizons: null,
      historical_prices: [],
    },
    research: {
      source: 'research',
      available: true,
      items: [
        {
          id: 'research_001', title: 'Acme Corp expands into new market', publisher: 'Example News',
          published_at: '2026-02-15T00:00:00+00:00', freshness: 'recent', relevance: '0.9',
          summary: 'Expansion summary.', url: 'https://example.com/a', source_type: 'news',
        },
        {
          id: 'research_002', title: 'Suspicious link article', publisher: 'Unknown',
          published_at: null, freshness: 'unknown', relevance: '0.3',
          summary: null, url: 'javascript:alert(1)', source_type: 'news',
        },
      ],
    },
    analyst: {
      source: 'analyst',
      available: true,
      investment_thesis: 'Acme Corp shows strong profitability.',
      investment_thesis_evidence: { financial: ['roe'], valuation: [], risk: [], research: ['research_001'] },
      strengths: ['Strong ROE'],
      weaknesses: ['High leverage'],
      category_analysis: [
        { category: 'profitability', text: 'Profitable.', evidence: { financial: ['roe'], valuation: [], risk: [], research: [] } },
        { category: 'risk', text: 'Leverage is a risk.', evidence: { financial: [], valuation: [], risk: ['high_debt_to_equity'], research: [] } },
      ],
      key_takeaways: ['ROE is a strength'],
      caveats: ['Limited periods available'],
    },
    evidence: { financial: ['roe'], valuation: ['dcf'], risk: ['high_debt_to_equity'], research: ['research_001'] },
    warnings: [
      { source: 'financial_analysis', code: null, message: 'Only two fiscal periods of data are available.' },
      { source: 'valuation', code: null, message: 'target EV/EBITDA multiple is missing' },
    ],
    metadata: { report_version: '1.0', generated_at: '2026-03-01T00:00:00+00:00', pipeline_version: '1.0', duration_ms: 5000 },
    ...overrides,
  }
}

/** A `ResearchRunResult` wrapping `report` in a `CombinedAnalysisResult`
 * envelope -- shared across `AnalysisPage.test.tsx` and the route-level
 * tests, replacing the ad hoc `runResult` helper previously duplicated
 * per test file. */
export function buildRunResult(
  report: InvestmentResearchReport,
  overrides: Partial<ResearchRunResult> = {},
): ResearchRunResult {
  const result: CombinedAnalysisResult = {
    company: { name: report.company.name, ticker: report.company.ticker },
    status: report.status,
    financial_analysis: null,
    valuation: null,
    scoring: null,
    research: null,
    analyst: null,
    report,
    warnings: [],
    metadata: { pipeline_version: '1.0', started_at: '', completed_at: '', duration_ms: 1 },
  }
  return {
    research_run_id: 'run-1',
    ticker: report.company.ticker ?? 'ACME',
    research_date: '2026-09-02',
    run_type: 'NORMAL',
    status: 'COMPLETED',
    is_new_run: true,
    started_at: '2026-09-02T10:00:00Z',
    completed_at: '2026-09-02T10:00:05Z',
    result,
    ...overrides,
  }
}
