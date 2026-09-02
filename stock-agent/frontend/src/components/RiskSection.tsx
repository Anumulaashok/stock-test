import type { ReportRiskIndicator, ReportRiskSection, Severity } from '../types/backend'
import { humanizeKey } from '../lib/format'
import { SeverityBadge } from './StatusBadge'

const BUCKETS: Array<{ key: keyof ReportRiskSection; severity: Severity | null; label: string }> = [
  { key: 'critical', severity: 'critical', label: 'Critical' },
  { key: 'high', severity: 'high', label: 'High' },
  { key: 'medium', severity: 'medium', label: 'Medium' },
  { key: 'low', severity: 'low', label: 'Low' },
  { key: 'informational', severity: null, label: 'Informational' },
]

function RiskRow({ indicator }: { indicator: ReportRiskIndicator }) {
  return (
    <li className="flex flex-col gap-1 border-b border-[var(--color-border)] py-2.5 last:border-0 sm:flex-row sm:items-baseline sm:justify-between">
      <div>
        <span className="font-medium">{humanizeKey(indicator.name)}</span>
        <p className="text-sm text-[var(--color-text-muted)]">{indicator.reason}</p>
      </div>
      <SeverityBadge severity={indicator.severity} />
    </li>
  )
}

export function RiskSection({ risk }: { risk: ReportRiskSection | null }) {
  if (!risk) {
    return (
      <section aria-labelledby="risk-heading">
        <h2 id="risk-heading" className="section-heading mb-3">
          Risk
        </h2>
        <p className="text-sm text-[var(--color-text-faint)]">Risk analysis is unavailable for this company.</p>
      </section>
    )
  }

  const nonEmpty = BUCKETS.filter((bucket) => risk[bucket.key].length > 0)

  return (
    <section aria-labelledby="risk-heading">
      <h2 id="risk-heading" className="section-heading mb-3">
        Risk
      </h2>
      {nonEmpty.length === 0 ? (
        <p className="text-sm text-[var(--color-text-faint)]">No risk indicators were reported.</p>
      ) : (
        <div className="space-y-4">
          {nonEmpty.map((bucket) =>
            bucket.key === 'informational' ? (
              <details key={bucket.key} className="group">
                <summary className="mb-1.5 flex cursor-pointer list-none items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
                  <span aria-hidden className="transition-transform group-open:rotate-90">▸</span>
                  {bucket.label}
                  <span className="normal-case text-[var(--color-text-faint)]">
                    ({(risk[bucket.key] as ReportRiskIndicator[]).length} evaluated, no action needed)
                  </span>
                </summary>
                <ul className="surface-card divide-y divide-[var(--color-border)] px-4">
                  {(risk[bucket.key] as ReportRiskIndicator[]).map((indicator) => (
                    <RiskRow key={indicator.name} indicator={indicator} />
                  ))}
                </ul>
              </details>
            ) : (
              <div key={bucket.key}>
                <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
                  {bucket.label}
                </h3>
                <ul className="surface-card divide-y divide-[var(--color-border)] px-4">
                  {(risk[bucket.key] as ReportRiskIndicator[]).map((indicator) => (
                    <RiskRow key={indicator.name} indicator={indicator} />
                  ))}
                </ul>
              </div>
            ),
          )}
        </div>
      )}
    </section>
  )
}
