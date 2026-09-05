import type { InvestmentResearchReport } from '../../types/backend'

export interface DiffRow {
  label: string
  oldValue: string | null
  newValue: string | null
  changed: boolean
}

function row(label: string, oldValue: string | null, newValue: string | null): DiffRow {
  return { label, oldValue, newValue, changed: oldValue !== newValue }
}

function countBySeverity(risk: InvestmentResearchReport['risk']): string {
  if (!risk) return '—'
  return `${risk.critical.length} critical, ${risk.high.length} high, ${risk.medium.length} medium, ${risk.low.length} low`
}

/**
 * Compares two past runs' reports field-by-field, using only equality
 * (`oldValue !== newValue`) to flag a change -- never a computed delta
 * or percentage (I2: that would be deriving a new statistic in
 * TypeScript from two backend-returned values, not reshaping). Every
 * value shown is exactly what the backend already returned for that
 * run; this function only pairs them up and flags inequality.
 */
export function buildRunDiffRows(oldReport: InvestmentResearchReport, newReport: InvestmentResearchReport): DiffRow[] {
  return [
    row('Overall score', oldReport.summary.overall_score, newReport.summary.overall_score),
    row('Score band', oldReport.summary.score_band, newReport.summary.score_band),
    row('Signal', oldReport.summary.signal?.label ?? null, newReport.summary.signal?.label ?? null),
    row('Investment thesis', oldReport.summary.investment_thesis, newReport.summary.investment_thesis),
    row('Current price', oldReport.market?.current_price ?? null, newReport.market?.current_price ?? null),
    row(
      'Valuation (current share price)',
      oldReport.valuation?.current_share_price ?? null,
      newReport.valuation?.current_share_price ?? null,
    ),
    row('Crossover signal', oldReport.forecast?.crossover?.signal ?? null, newReport.forecast?.crossover?.signal ?? null),
    row('Risk indicators', countBySeverity(oldReport.risk), countBySeverity(newReport.risk)),
  ]
}
