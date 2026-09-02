/**
 * The backend runs one synchronous pipeline call with no stage-progress
 * API — so this deliberately does NOT show a fake staged checklist
 * ("✓ Fetching data... ✓ Scoring..."). That would misrepresent what the
 * app actually knows. It shows one honest, indeterminate loading state
 * plus a note about why it can take a while.
 */
export function LoadingState({ ticker }: { ticker: string }) {
  return (
    <div role="status" aria-live="polite" className="animate-fade-in-up flex flex-col items-center gap-4 py-20 text-center">
      <div className="relative flex h-14 w-14 items-center justify-center">
        <span
          aria-hidden="true"
          className="absolute inset-0 animate-ping rounded-full bg-[var(--color-accent)]/15"
        />
        <div
          className="h-10 w-10 animate-spin rounded-full border-[3px] border-[var(--color-border)] border-t-[var(--color-accent)]"
          aria-hidden="true"
        />
      </div>
      <p className="font-mono-nums text-lg font-semibold">Analyzing {ticker}…</p>
      <p className="max-w-sm text-sm text-[var(--color-text-faint)]">
        Running financial data retrieval, valuation, scoring, research lookup, and AI analyst generation on the
        backend. This can take up to a minute or two.
      </p>
    </div>
  )
}
