import type { InvestmentResearchReport } from '../types/backend'

/**
 * Looks up the actual computed value behind each evidence name the AI
 * analyst cites, so "Why does the AI say this?" can show e.g. "ROE:
 * 24.8%" instead of a bare metric name -- every value comes from the
 * same deterministic sections already rendered elsewhere on the page
 * (financials/valuation/risk), never recomputed or invented here.
 */
export function buildEvidenceValueMap(report: InvestmentResearchReport): Record<string, string> {
  const map: Record<string, string> = {}

  if (report.financials) {
    for (const metrics of [
      report.financials.profitability,
      report.financials.growth,
      report.financials.financial_health,
      report.financials.cash_flow,
      report.financials.other,
    ]) {
      for (const metric of metrics) {
        if (metric.formatted_value) map[metric.name] = metric.formatted_value
      }
    }
  }

  if (report.scoring) {
    for (const category of report.scoring.categories) {
      if (category.score) map[category.category] = `${Number(category.score).toFixed(1)}/100`
    }
  }

  if (report.valuation) {
    for (const method of report.valuation.methods) {
      if (method.formatted_value_per_share) map[method.method] = method.formatted_value_per_share
    }
  }

  if (report.risk) {
    for (const indicator of [
      ...report.risk.critical,
      ...report.risk.high,
      ...report.risk.medium,
      ...report.risk.low,
      ...report.risk.informational,
    ]) {
      if (indicator.reason) map[indicator.name] = indicator.reason
    }
  }

  return map
}
