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
    <div role="alert" className="rounded border border-[var(--color-status-critical)]/40 bg-[var(--color-status-critical)]/10 p-3 text-sm">
      <p className="font-medium text-[var(--color-status-critical)]">Could not complete analysis</p>
      <p className="mt-1 text-[var(--color-text-muted)]">{message}</p>
    </div>
  )
}
