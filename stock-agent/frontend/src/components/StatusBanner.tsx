import type { ReportStatus } from '../types/backend'

interface StatusBannerProps {
  status: ReportStatus
  ticker: string
}

/** Reflects the backend's own `report.status` — never a frontend guess. */
export function StatusBanner({ status, ticker }: StatusBannerProps) {
  if (status === 'calculated') return null

  if (status === 'partial') {
    return (
      <div
        role="status"
        className="rounded border border-[var(--color-status-medium)]/40 bg-[var(--color-status-medium)]/10 p-3 text-sm"
      >
        <p className="font-medium text-[var(--color-status-medium)]">Analysis partially completed</p>
        <p className="mt-1 text-[var(--color-text-muted)]">
          Deterministic financial analysis, valuation, and scoring for {ticker} completed successfully. One or more
          optional stages (AI analyst and/or research) did not complete — see Warnings below for details.
        </p>
      </div>
    )
  }

  return (
    <div role="alert" className="rounded border border-[var(--color-status-critical)]/40 bg-[var(--color-status-critical)]/10 p-3 text-sm">
      <p className="font-medium text-[var(--color-status-critical)]">Analysis failed</p>
      <p className="mt-1 text-[var(--color-text-muted)]">
        The analysis for {ticker} could not be completed. See Warnings below for the reason reported by the backend.
      </p>
    </div>
  )
}
