/**
 * The backend runs one synchronous pipeline call with no stage-progress
 * API — so this deliberately does NOT show a fake staged checklist
 * ("✓ Fetching data... ✓ Scoring..."). That would misrepresent what the
 * app actually knows. It shows one honest, indeterminate loading state
 * plus a note about why it can take a while.
 */
export function LoadingState({ ticker }: { ticker: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col items-center gap-3 py-16 text-center">
      <div
        className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-border-strong)] border-t-[var(--color-accent)]"
        aria-hidden="true"
      />
      <p className="text-lg font-medium">Analyzing {ticker}…</p>
      <p className="max-w-sm text-sm text-[var(--color-text-faint)]">
        This runs financial data retrieval, valuation, scoring, research lookup, and AI analyst generation on the
        backend. It can take up to a minute or two.
      </p>
    </div>
  )
}
