/** Content-shaped loading placeholder -- replaces bare "Loading…" text.
 * Sized by the caller via className (width/height utilities). */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden="true" className={`skeleton ${className}`} />
}

/** A stack of skeleton rows, for list-shaped content. */
export function SkeletonRows({ count = 3, className = '' }: { count?: number; className?: string }) {
  return (
    <div className={`flex flex-col gap-2 ${className}`} role="status" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-4 w-full" />
      ))}
    </div>
  )
}

/** Mirrors `WatchlistList`'s row shape (ticker + price + change, one
 * card per row) instead of generic bare lines. */
export function SkeletonWatchlistRows({ count = 3 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-2" role="status" aria-label="Loading watchlist">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="surface-card flex items-center justify-between gap-2 px-4 py-3">
          <Skeleton className="h-4 w-24" />
          <div className="flex items-center gap-4">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-12" />
            <Skeleton className="h-4 w-14" />
          </div>
        </div>
      ))}
    </div>
  )
}

/** Mirrors `HoldingsTable`'s column shape (ticker/qty/cost/price/value/gain)
 * instead of generic bare lines. */
export function SkeletonHoldingsTable({ count = 3 }: { count?: number }) {
  return (
    <div className="surface-card overflow-hidden" role="status" aria-label="Loading holdings">
      <div className="flex gap-4 px-3 py-2" style={{ borderBottom: '1px solid var(--color-border)' }}>
        {['Ticker', 'Quantity', 'Avg Cost', 'Price', 'Value', 'Gain / Loss'].map((label) => (
          <span key={label} className="metric-label flex-1">
            {label}
          </span>
        ))}
      </div>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-3 py-2.5" style={{ borderTop: i > 0 ? '1px solid var(--color-border)' : undefined }}>
          {Array.from({ length: 6 }).map((__, col) => (
            <Skeleton key={col} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}
