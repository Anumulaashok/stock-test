import { ApiError } from '../api/client'

const FRIENDLY_MESSAGE: Record<ApiError['kind'], string> = {
  network: 'Could not reach the analysis server. Check your connection and try again.',
  timeout: 'The request took too long and was cancelled. Please try again.',
  client: 'The request could not be processed.',
  server: 'The analysis server encountered an unexpected error. Please try again shortly.',
}

/** For transport-level failures (network/timeout/HTTP error) -- distinct
 * from `report.status === "failed"`, which is a successful response the
 * backend structured on purpose (see `StatusBanner`). Never renders raw
 * exception text or a stack trace. */
export function ErrorBanner({ error }: { error: ApiError }) {
  const message = error.kind === 'client' && error.message ? error.message : FRIENDLY_MESSAGE[error.kind]
  return (
    <div
      role="alert"
      className="mx-auto flex max-w-lg items-start gap-3 rounded-[var(--radius-md)] border border-[var(--color-status-critical)]/25 bg-[var(--color-status-critical)]/8 p-4 shadow-[var(--shadow-xs)]"
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 20 20"
        fill="none"
        className="mt-0.5 h-5 w-5 shrink-0 text-[var(--color-status-critical)]"
      >
        <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.6" />
        <path d="M10 6.5V11" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="10" cy="13.6" r="0.9" fill="currentColor" />
      </svg>
      <div className="text-sm">
        <p className="font-semibold text-[var(--color-status-critical)]">Could not complete analysis</p>
        <p className="mt-0.5 text-[var(--color-text-muted)]">{message}</p>
      </div>
    </div>
  )
}
