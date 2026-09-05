import { buildRunDiffRows } from './researchRunDiff'
import type { InvestmentResearchReport } from '../../types/backend'

/**
 * Two past runs' reports, side by side -- every value is exactly what
 * the backend returned for that run (no computed delta/percentage,
 * I2). A changed row is highlighted by simple inequality, not by how
 * large the change is.
 */
export function ResearchRunDiffView({
  oldLabel,
  newLabel,
  oldReport,
  newReport,
}: {
  oldLabel: string
  newLabel: string
  oldReport: InvestmentResearchReport
  newReport: InvestmentResearchReport
}) {
  const rows = buildRunDiffRows(oldReport, newReport)

  return (
    <div className="surface-card overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-text-faint)]">
            <th className="px-3 py-2 font-medium">Field</th>
            <th className="px-3 py-2 font-medium">{oldLabel}</th>
            <th className="px-3 py-2 font-medium">{newLabel}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--color-border)]">
          {rows.map((row) => (
            <tr key={row.label} className={row.changed ? 'bg-[var(--color-accent-soft)]/40' : undefined}>
              <td className="px-3 py-2 text-[var(--color-text-faint)]">{row.label}</td>
              <td className="px-3 py-2 font-mono-nums">{row.oldValue ?? '—'}</td>
              <td className="px-3 py-2 font-mono-nums">
                {row.newValue ?? '—'}
                {row.changed && <span className="ml-1.5 text-[10px] uppercase text-[var(--color-accent-strong)]">Changed</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="support-text px-3 py-2 text-xs">
        Values only -- no computed change/percentage. "Changed" means the two runs' values are literally different.
      </p>
    </div>
  )
}
