/** Presentational only -- all watchlist API calls live in `AnalysisPage`,
 * which owns the ticker/auth state this button needs. Uses the existing
 * `/api/v1/watchlist` endpoints via `api/portfolio.ts`, never a local
 * fake watchlist. */
export function WatchlistButton({
  status,
  inWatchlist,
  pending,
  error,
  onToggle,
}: {
  status: 'checking' | 'authenticated' | 'anonymous'
  inWatchlist: boolean | null
  pending: boolean
  error: string | null
  onToggle: () => void
}) {
  if (status !== 'authenticated') {
    return (
      <span
        title="Log in to save companies to your watchlist"
        className="inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium text-[var(--color-text-faint)]"
      >
        <StarIcon filled={false} />
        Watchlist
      </span>
    )
  }

  if (inWatchlist === null) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border)] px-3 py-1.5 text-sm text-[var(--color-text-faint)]">
        <StarIcon filled={false} />
        Watchlist
      </span>
    )
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={onToggle}
        disabled={pending}
        aria-pressed={inWatchlist}
        className={`inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] border px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
          inWatchlist
            ? 'border-[var(--color-accent)]/40 bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]'
            : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]'
        }`}
      >
        <StarIcon filled={inWatchlist} />
        {pending ? 'Saving…' : inWatchlist ? 'In Watchlist' : 'Add to Watchlist'}
      </button>
      {error && <span className="text-xs text-[var(--color-status-negative)]">{error}</span>}
    </div>
  )
}

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.4">
      <path
        strokeLinejoin="round"
        d="M10 2.5l2.25 4.56 5.03.73-3.64 3.55.86 5.01L10 13.9l-4.5 2.37.86-5.01-3.64-3.55 5.03-.73L10 2.5z"
      />
    </svg>
  )
}
