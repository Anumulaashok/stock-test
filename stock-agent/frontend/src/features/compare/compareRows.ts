import { humanizeKey } from '../../lib/format'
import type { InvestmentResearchReport, ReportFinancialMetric } from '../../types/backend'

export interface CompareCell {
  ticker: string
  formattedValue: string | null
  /** Raw numeric value, used only to pick a best/worst cell -- never
   * displayed directly (the cell always shows `formattedValue`, the
   * backend's own formatting). `null` when unavailable or not parseable. */
  rawValue: number | null
}

export interface CompareRow {
  label: string
  cells: CompareCell[]
  /** Set only for rows where "higher is better" is an unambiguous,
   * already-established convention elsewhere in this app (overall
   * score, valuation upside) -- ticker of the best/worst cell among
   * those with a value, or null when there's a tie or nothing to
   * compare. Never set for raw financial metrics (ROE vs. debt/equity
   * have opposite "better" directions and there's no per-metric
   * directionality registry in this codebase to draw on safely). */
  bestTicker: string | null
  worstTicker: string | null
}

function toNumber(value: string | null): number | null {
  if (value === null) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function bestWorst(cells: CompareCell[]): { bestTicker: string | null; worstTicker: string | null } {
  const withValue = cells.filter((c): c is CompareCell & { rawValue: number } => c.rawValue !== null)
  if (withValue.length < 2) return { bestTicker: null, worstTicker: null }
  const best = withValue.reduce((a, b) => (b.rawValue > a.rawValue ? b : a))
  const worst = withValue.reduce((a, b) => (b.rawValue < a.rawValue ? b : a))
  if (best.rawValue === worst.rawValue) return { bestTicker: null, worstTicker: null }
  return { bestTicker: best.ticker, worstTicker: worst.ticker }
}

/** Score/band/price/signal header rows -- one row per attribute, one
 * cell per ticker. Only the score row gets best/worst (higher-is-
 * better is the one directionality convention already established
 * throughout this app, e.g. ScoreBand ordering). */
export function buildSummaryRows(reports: (InvestmentResearchReport | null)[], tickers: string[]): CompareRow[] {
  const scoreCells = reports.map((r, i) => ({
    ticker: tickers[i], formattedValue: r?.summary.overall_score ?? null, rawValue: toNumber(r?.summary.overall_score ?? null),
  }))
  const priceCells = reports.map((r, i) => ({
    ticker: tickers[i], formattedValue: r?.market?.formatted_current_price ?? null, rawValue: null,
  }))
  const bandCells = reports.map((r, i) => ({ ticker: tickers[i], formattedValue: r?.summary.score_band ?? null, rawValue: null }))
  const signalCells = reports.map((r, i) => ({ ticker: tickers[i], formattedValue: r?.summary.signal?.label ?? null, rawValue: null }))

  return [
    { label: 'Overall score', cells: scoreCells, ...bestWorst(scoreCells) },
    { label: 'Band', cells: bandCells, bestTicker: null, worstTicker: null },
    { label: 'Signal', cells: signalCells, bestTicker: null, worstTicker: null },
    { label: 'Current price', cells: priceCells, bestTicker: null, worstTicker: null },
  ]
}

/** One row per valuation method present on ANY of the compared
 * reports (union, not intersection) -- a method absent for one ticker
 * still gets a row, with that ticker's cell reading unavailable.
 * Upside/downside gets best/worst: for the SAME method across tickers,
 * "higher upside" being more attractive is the method's own stated
 * semantics (`upside_downside_percent`), not a directionality this
 * code is inventing. */
export function buildValuationRows(reports: (InvestmentResearchReport | null)[], tickers: string[]): CompareRow[] {
  const methodNames = Array.from(new Set(reports.flatMap((r) => r?.valuation?.methods.map((m) => m.method) ?? [])))

  return methodNames.map((method) => {
    const cells = reports.map((r, i) => {
      const found = r?.valuation?.methods.find((m) => m.method === method)
      return {
        ticker: tickers[i],
        formattedValue: found?.formatted_upside_downside ?? found?.formatted_value_per_share ?? null,
        rawValue: toNumber(found?.upside_downside_percent ?? null),
      }
    })
    return { label: humanizeKey(method), cells, ...bestWorst(cells) }
  })
}

function collectMetrics(report: InvestmentResearchReport | null): ReportFinancialMetric[] {
  if (!report?.financials) return []
  return [...report.financials.profitability, ...report.financials.growth, ...report.financials.financial_health, ...report.financials.cash_flow]
}

/** One row per financial metric name present on ANY compared report.
 * No best/worst -- these metrics don't share one "higher is better"
 * direction (ROE does, debt/equity doesn't), and there is no per-
 * metric directionality registry in this codebase to draw on safely;
 * showing every ticker's real value side by side is the honest,
 * conservative version of this row. */
export function buildFinancialMetricRows(reports: (InvestmentResearchReport | null)[], tickers: string[]): CompareRow[] {
  const names = Array.from(new Set(reports.flatMap((r) => collectMetrics(r).map((m) => m.name))))

  return names.map((name) => {
    const cells = reports.map((r, i) => {
      const found = collectMetrics(r).find((m) => m.name === name)
      return { ticker: tickers[i], formattedValue: found?.formatted_value ?? null, rawValue: null }
    })
    return { label: humanizeKey(name), cells, bestTicker: null, worstTicker: null }
  })
}

/** Risk indicator counts by severity -- a plain count reshaped from
 * arrays each report already carries, never a computed statistic. No
 * best/worst: severity counts are informative, not a ranking this
 * feature should imply a "winner" for. */
export function buildRiskRows(reports: (InvestmentResearchReport | null)[], tickers: string[]): CompareRow[] {
  const severities: { key: 'critical' | 'high' | 'medium' | 'low'; label: string }[] = [
    { key: 'critical', label: 'Critical risk indicators' },
    { key: 'high', label: 'High risk indicators' },
    { key: 'medium', label: 'Medium risk indicators' },
    { key: 'low', label: 'Low risk indicators' },
  ]
  return severities.map(({ key, label }) => ({
    label,
    cells: reports.map((r, i) => ({
      ticker: tickers[i], formattedValue: r?.risk ? String(r.risk[key].length) : null, rawValue: null,
    })),
    bestTicker: null,
    worstTicker: null,
  }))
}
