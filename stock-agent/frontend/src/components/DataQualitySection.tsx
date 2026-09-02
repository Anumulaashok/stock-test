import type { InvestmentResearchReport } from '../types/backend'

/**
 * A compact data-completeness summary, derived entirely from the
 * per-metric `status` fields already present in `report.financials`/
 * `report.valuation`/`report.risk` -- never a backend-reported
 * confidence score (none exists) and never a fabricated percentage.
 * The qualitative label (High/Moderate/Low) is a documented threshold
 * over the real evaluated/total ratio, the same "recolor what's already
 * computed" pattern as `compute_signal`/`compute_technical_signal`.
 */

function countStatuses(report: InvestmentResearchReport): { calculated: number; total: number } {
  let calculated = 0
  let total = 0

  if (report.financials) {
    for (const metrics of [
      report.financials.profitability,
      report.financials.growth,
      report.financials.financial_health,
      report.financials.cash_flow,
      report.financials.other,
    ]) {
      for (const metric of metrics) {
        total += 1
        if (metric.status === 'calculated') calculated += 1
      }
    }
  }

  if (report.valuation) {
    for (const method of report.valuation.methods) {
      total += 1
      if (method.status === 'calculated') calculated += 1
    }
  }

  if (report.risk) {
    for (const indicator of [...report.risk.critical, ...report.risk.high, ...report.risk.medium, ...report.risk.low, ...report.risk.informational]) {
      total += 1
      if (indicator.status === 'calculated') calculated += 1
    }
  }

  return { calculated, total }
}

function confidenceLabel(ratio: number): { label: string; color: string } {
  if (ratio >= 0.85) return { label: 'High confidence', color: 'var(--color-status-positive)' }
  if (ratio >= 0.6) return { label: 'Moderate confidence', color: 'var(--color-status-medium)' }
  return { label: 'Low confidence', color: 'var(--color-status-high)' }
}

export function DataQualitySection({ report }: { report: InvestmentResearchReport }) {
  const { calculated, total } = countStatuses(report)
  if (total === 0) return null

  const ratio = calculated / total
  const confidence = confidenceLabel(ratio)
  const unavailable = total - calculated

  return (
    <section aria-labelledby="data-quality-heading" className="surface-card p-4">
      <h2 id="data-quality-heading" className="section-heading mb-2">
        Data Quality
      </h2>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: confidence.color }} />
        <span className="font-medium" style={{ color: confidence.color }}>
          {confidence.label}
        </span>
        <span className="text-[var(--color-text-faint)]">
          — {calculated} of {total} metrics evaluated
          {unavailable > 0 && `, ${unavailable} unavailable`}
        </span>
      </div>
      <p className="mt-1 text-xs text-[var(--color-text-faint)]">
        Derived from the status of every financial, valuation, and risk metric on this page — see Data Quality &amp;
        Warnings below for the specific reasons.
      </p>
    </section>
  )
}
