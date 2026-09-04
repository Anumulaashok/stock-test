import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { friendlyErrorMessage } from '../../components/ui/ErrorState'
import { formatDate, formatSignedPercent, toDisplayNumber } from '../../lib/format'
import { paths } from '../../routes/paths'
import type { WatchlistItemEnriched } from '../../types/backend'

function changeColor(changePercent: string | null): string {
  if (changePercent === null) return 'text-[var(--color-text-faint)]'
  return Number(changePercent) >= 0 ? 'text-[var(--color-status-positive)]' : 'text-[var(--color-status-negative)]'
}

export function WatchlistList({
  items,
  onRemove,
}: {
  items: WatchlistItemEnriched[]
  onRemove: (ticker: string) => Promise<void>
}) {
  if (items.length === 0) {
    return (
      <div className="surface-card flex flex-col items-center gap-1 p-8 text-center">
        <p className="card-heading">Your watchlist is empty</p>
        <p className="support-text">Add a ticker above to start tracking it here.</p>
      </div>
    )
  }

  return (
    <ul className="flex flex-col gap-2">
      {items.map((item) => (
        <WatchlistRow key={item.ticker} item={item} onRemove={onRemove} />
      ))}
    </ul>
  )
}

/** Removing asks for an explicit, named confirm ("Remove RELIANCE?")
 * rather than a generic browser dialog, and only reflects the removal
 * once the backend call actually succeeds -- the row never disappears
 * optimistically. */
function WatchlistRow({
  item,
  onRemove,
}: {
  item: WatchlistItemEnriched
  onRemove: (ticker: string) => Promise<void>
}) {
  const [confirming, setConfirming] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    setRemoving(true)
    setError(null)
    try {
      await onRemove(item.ticker)
    } catch (err) {
      setError(err instanceof ApiError ? friendlyErrorMessage(err) : 'Could not remove this ticker.')
      setRemoving(false)
      setConfirming(false)
    }
  }

  return (
    <li className="surface-card flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-0.5">
        <span className="font-mono-nums text-sm font-semibold text-[var(--color-text)]">{item.ticker}</span>
        <span className="support-text">Added {formatDate(item.created_at) ?? '—'}</span>
      </div>

      <div className="flex items-center gap-4">
        <div className="text-right">
          {item.current_price !== null ? (
            <>
              <div className="font-mono-nums text-sm font-semibold">
                {toDisplayNumber(item.current_price, 2)}
              </div>
              <div className={`font-mono-nums text-xs ${changeColor(item.change_percent)}`}>
                {formatSignedPercent(item.change_percent) ?? '—'}
              </div>
            </>
          ) : (
            <div className="text-xs text-[var(--color-text-faint)]">Price unavailable</div>
          )}
        </div>
        <div className="text-right">
          {item.overall_score !== null ? (
            <div className="metric-value text-sm">{toDisplayNumber(item.overall_score, 0)}</div>
          ) : (
            <div className="text-xs text-[var(--color-text-faint)]" title="This ticker has never been researched">
              Not researched
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Link to={paths.stock(item.ticker)} className="btn-secondary px-3 py-1.5 text-xs">
          View
        </Link>

        {confirming ? (
          <>
            <span className="text-xs text-[var(--color-status-negative)]">Remove {item.ticker}?</span>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={removing}
              className="rounded-[var(--radius-sm)] border border-[var(--color-status-negative)]/50 bg-[var(--color-status-negative)]/10 px-3 py-1.5 text-xs font-medium text-[var(--color-status-negative)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {removing ? 'Removing…' : 'Confirm'}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              disabled={removing}
              className="text-xs text-[var(--color-text-faint)] underline disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="text-xs text-[var(--color-status-negative)] underline"
          >
            Remove
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="text-xs text-[var(--color-status-negative)] sm:basis-full">
          {error}
        </p>
      )}
    </li>
  )
}
