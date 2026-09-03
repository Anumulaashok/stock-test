import type { ReportRiskIndicator, ReportRiskSection } from '../../types/backend'
import { humanizeKey } from '../../lib/format'
import { SeverityBadge } from '../StatusBadge'
import { Disclosure } from '../ui/Disclosure'
import { EmptyState } from '../SectionHeader'

/** §8/§9, redesigned around the real severity buckets the backend
 * produces -- there is no 0-100 risk score or per-domain sub-scores in
 * this codebase (financial/valuation/market/cashflow/liquidity/
 * technical risk quadrants do not exist), so this shows a qualitative
 * headline built from real counts, then every indicator expandable to
 * its real reason/value/threshold. */
export function RiskOverview({ risk }: { risk: ReportRiskSection | null }) {
  if (!risk) {
    return <EmptyState title="Risk analysis unavailable" reason="Risk analysis did not run for this company." />
  }

  const counts = {
    critical: risk.critical.length,
    high: risk.high.length,
    medium: risk.medium.length,
    low: risk.low.length,
  }
  const total = counts.critical + counts.high + counts.medium + counts.low

  const headline =
    counts.critical > 0
      ? { label: 'Critical Risk', color: 'var(--color-status-critical)' }
      : counts.high > 0
        ? { label: 'High Risk', color: 'var(--color-status-high)' }
        : counts.medium > 0
          ? { label: 'Moderate Risk', color: 'var(--color-status-medium)' }
          : total > 0
            ? { label: 'Low Risk', color: 'var(--color-status-positive)' }
            : { label: 'No risk indicators flagged', color: 'var(--color-text-faint)' }

  const summaryParts = [
    counts.critical > 0 && `${counts.critical} critical`,
    counts.high > 0 && `${counts.high} high`,
    counts.medium > 0 && `${counts.medium} medium`,
    counts.low > 0 && `${counts.low} low`,
  ].filter(Boolean)

  const buckets: Array<{ key: keyof ReportRiskSection; label: string }> = [
    { key: 'critical', label: 'Critical' },
    { key: 'high', label: 'High' },
    { key: 'medium', label: 'Medium' },
    { key: 'low', label: 'Low' },
  ]

  return (
    <section aria-labelledby="risk-overview-heading" className="surface-card p-5">
      <h2 id="risk-overview-heading" className="section-heading mb-3">
        Risk Overview
      </h2>
      <div className="mb-4">
        <div className="text-lg font-bold" style={{ color: headline.color }}>
          {headline.label}
        </div>
        {summaryParts.length > 0 && <div className="text-xs text-[var(--color-text-faint)]">{summaryParts.join(' · ')}</div>}
      </div>

      <div className="flex flex-col divide-y divide-[var(--color-border)]">
        {buckets
          .filter((bucket) => risk[bucket.key].length > 0)
          .flatMap((bucket) => risk[bucket.key] as ReportRiskIndicator[])
          .map((indicator) => (
            <div key={indicator.name} className="py-2">
              <Disclosure
                summary={<span className="font-medium">{humanizeKey(indicator.name)}</span>}
                meta={<SeverityBadge severity={indicator.severity} />}
              >
                <p>{indicator.reason}</p>
                {indicator.value !== null && (
                  <p className="mt-1 font-mono-nums text-xs text-[var(--color-text-faint)]">
                    Value: {indicator.value}
                    {indicator.threshold !== null && ` · Threshold: ${indicator.threshold}`}
                  </p>
                )}
              </Disclosure>
            </div>
          ))}
      </div>

      {risk.informational.length > 0 && (
        <Disclosure summary={<span className="text-xs uppercase tracking-wide text-[var(--color-text-faint)]">{risk.informational.length} evaluated, no action needed</span>} defaultOpen={false}>
          <div className="flex flex-col gap-2 pt-1">
            {risk.informational.map((indicator) => (
              <div key={indicator.name}>
                <span className="font-medium">{humanizeKey(indicator.name)}</span>
                <p className="support-text">{indicator.reason}</p>
              </div>
            ))}
          </div>
        </Disclosure>
      )}
    </section>
  )
}
