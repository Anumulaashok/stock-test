import type { ReportFinancialMetric, ReportFinancialSection } from '../types/backend'
import { humanizeKey } from '../lib/format'
import { MetricStatusBadge } from './StatusBadge'

function MetricTable({ metrics }: { metrics: ReportFinancialMetric[] }) {
  if (metrics.length === 0) {
    return <p className="text-sm text-[var(--color-text-faint)]">No metrics in this category.</p>
  }
  return (
    <table className="w-full text-sm">
      <tbody>
        {metrics.map((metric) => (
          <tr key={metric.name} className="border-b border-[var(--color-border)] last:border-0">
            <th scope="row" className="py-2 pr-3 text-left font-normal text-[var(--color-text-muted)]">
              {humanizeKey(metric.name)}
            </th>
            <td className="py-2 pr-3 text-right font-mono-nums font-medium">
              {metric.formatted_value ?? <span className="font-normal text-[var(--color-text-faint)]">—</span>}
            </td>
            <td className="py-2 text-right">
              {metric.status !== 'calculated' ? (
                <span title={metric.reason ?? undefined}>
                  <MetricStatusBadge status={metric.status} />
                </span>
              ) : (
                <span className="text-xs text-[var(--color-text-faint)]">Calculated</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const CATEGORY_LABEL: Record<string, string> = {
  profitability: 'Profitability',
  growth: 'Growth',
  financial_health: 'Financial Health',
  cash_flow: 'Cash Flow',
  other: 'Other',
}

export function FinancialSection({ financials }: { financials: ReportFinancialSection | null }) {
  if (!financials) {
    return (
      <section aria-labelledby="financials-heading">
        <h2 id="financials-heading" className="section-heading mb-3">
          Financial Analysis
        </h2>
        <p className="text-sm text-[var(--color-text-faint)]">Financial analysis is unavailable for this company.</p>
      </section>
    )
  }

  const groups: Array<[string, ReportFinancialMetric[]]> = [
    ['profitability', financials.profitability],
    ['growth', financials.growth],
    ['financial_health', financials.financial_health],
    ['cash_flow', financials.cash_flow],
  ].filter(([, metrics]) => metrics.length > 0) as Array<[string, ReportFinancialMetric[]]>

  if (financials.other.length > 0) groups.push(['other', financials.other])

  return (
    <section aria-labelledby="financials-heading">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="financials-heading" className="section-heading">
          Financial Analysis
        </h2>
        {financials.periods_analyzed.length > 0 && (
          <span className="text-xs text-[var(--color-text-faint)]">
            Periods: {financials.periods_analyzed.join(', ')}
          </span>
        )}
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {groups.map(([key, metrics]) => (
          <div key={key} className="surface-card p-4">
            <h3 className="mb-1.5 text-sm font-semibold text-[var(--color-text)]">{CATEGORY_LABEL[key] ?? humanizeKey(key)}</h3>
            <MetricTable metrics={metrics} />
          </div>
        ))}
      </div>
    </section>
  )
}
