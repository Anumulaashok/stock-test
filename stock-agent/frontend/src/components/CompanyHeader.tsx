import type { InvestmentResearchReport } from '../types/backend'
import { toDisplayNumber } from '../lib/format'

const STATUS_LABEL: Record<string, string> = {
  calculated: 'Complete',
  partial: 'Partially complete',
  failed: 'Failed',
}

export function CompanyHeader({ report }: { report: InvestmentResearchReport }) {
  const price = toDisplayNumber(report.valuation?.current_share_price)
  const score = toDisplayNumber(report.summary.overall_score)

  return (
    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--color-border)] pb-4">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">
          {report.company.name}
          {report.company.ticker && (
            <span className="ml-2 font-mono-nums text-lg font-normal text-[var(--color-text-muted)]">
              {report.company.ticker}
            </span>
          )}
        </h1>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          Report status: <span className="font-medium">{STATUS_LABEL[report.status] ?? report.status}</span>
          {' · '}
          Generated {new Date(report.metadata.generated_at).toLocaleString()}
        </p>
      </div>

      <div className="flex gap-6 text-right">
        {price !== null && (
          <div>
            <div className="text-xs uppercase tracking-wide text-[var(--color-text-faint)]">Current Price</div>
            <div className="font-mono-nums text-xl font-semibold">${price}</div>
          </div>
        )}
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--color-text-faint)]">Overall Score</div>
          <div className="font-mono-nums text-xl font-semibold">
            {score !== null ? `${score} / 100` : 'Unavailable'}
          </div>
          {report.summary.score_band && (
            <div className="text-xs capitalize text-[var(--color-text-muted)]">{report.summary.score_band}</div>
          )}
        </div>
      </div>
    </div>
  )
}
