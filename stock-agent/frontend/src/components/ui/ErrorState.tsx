import { ApiError } from '../../api/client'

/** Shared transport-error copy -- previously duplicated verbatim in
 * ErrorBanner, AskAssistantSection, and StickyAskAssistant. Never shows
 * a raw status code or exception message to the user; the real detail
 * still goes to console.error at the call site. */
export const FRIENDLY_MESSAGE: Record<ApiError['kind'], string> = {
  network: 'Could not reach the server. Check your connection and try again.',
  timeout: 'The request took too long and was cancelled. Please try again.',
  client: 'The request could not be processed.',
  server: 'The server encountered an unexpected error. Please try again shortly.',
}

export function friendlyErrorMessage(error: ApiError): string {
  return error.kind === 'client' && error.message ? error.message : FRIENDLY_MESSAGE[error.kind]
}

/** A section-scoped error state with an explanation and a retry action --
 * never raw backend errors (§19). Distinct from `ErrorBanner`, which is
 * the page-level transport-failure banner; this is for a single section
 * failing to load while the rest of the page is fine. */
export function ErrorState({
  title = 'Something went wrong',
  error,
  onRetry,
}: {
  title?: string
  error: ApiError | string
  onRetry?: () => void
}) {
  const message = typeof error === 'string' ? error : friendlyErrorMessage(error)
  return (
    <div role="alert" className="surface-card flex flex-col items-start gap-2 p-4 text-sm">
      <p className="font-medium text-[var(--color-status-critical)]">{title}</p>
      <p className="support-text">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-secondary mt-1 px-3 py-1.5 text-xs">
          Retry
        </button>
      )}
    </div>
  )
}
