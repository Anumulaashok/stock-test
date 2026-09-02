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
        className="flex items-start gap-3 rounded-[var(--radius-md)] border border-[var(--color-status-medium)]/30 bg-[var(--color-status-medium)]/8 p-4 shadow-[var(--shadow-xs)]"
      >
        <span
          aria-hidden="true"
          className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[var(--color-status-medium)]"
        />
        <div className="text-sm">
          <p className="font-semibold text-[var(--color-status-medium)]">Analysis partially completed</p>
          <p className="mt-1 text-[var(--color-text-muted)]">
            Deterministic financial analysis, valuation, and scoring for {ticker} completed successfully. One or
            more optional stages (AI analyst and/or research) did not complete — see Warnings below for details.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-[var(--radius-md)] border border-[var(--color-status-critical)]/30 bg-[var(--color-status-critical)]/8 p-4 shadow-[var(--shadow-xs)]"
    >
      <span aria-hidden="true" className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[var(--color-status-critical)]" />
      <div className="text-sm">
        <p className="font-semibold text-[var(--color-status-critical)]">Analysis failed</p>
        <p className="mt-1 text-[var(--color-text-muted)]">
          The analysis for {ticker} could not be completed. See Warnings below for the reason reported by the
          backend.
        </p>
      </div>
    </div>
  )
}
