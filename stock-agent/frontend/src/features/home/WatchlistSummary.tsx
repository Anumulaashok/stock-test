import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useAsync } from '../../hooks/useAsync'
import { AsyncSection } from '../../components/ui/AsyncSection'
import { SkeletonRows } from '../../components/ui/Skeleton'
import { fetchWatchlist } from '../../api/portfolio'
import { paths } from '../../routes/paths'

const PREVIEW_LIMIT = 8

/** Count + a preview of tickers from the auth-gated `GET
 * /api/v1/watchlist` -- shows a graceful signed-out state instead of
 * disappearing or crashing when the viewer is anonymous. */
export function WatchlistSummary() {
  const { status } = useAuth()
  const state = useAsync(fetchWatchlist, [], { enabled: status === 'authenticated' })

  return (
    <section className="surface-card flex flex-col gap-3 p-4" aria-labelledby="watchlist-summary-heading">
      <div className="flex items-center justify-between gap-2">
        <h2 id="watchlist-summary-heading" className="card-heading">
          Watchlist
        </h2>
        <Link to={paths.watchlist()} className="text-xs font-medium text-[var(--color-accent-strong)] hover:underline">
          View all
        </Link>
      </div>

      {status === 'checking' && <SkeletonRows count={3} />}

      {status === 'anonymous' && (
        <p className="support-text">
          <Link to={paths.login()} className="font-medium text-[var(--color-accent-strong)] hover:underline">
            Sign in
          </Link>{' '}
          to see your watchlist.
        </p>
      )}

      {status === 'authenticated' && (
        <AsyncSection state={state} onRetry={state.reload} errorTitle="Could not load your watchlist">
          {(items) =>
            items.length === 0 ? (
              <p className="support-text">Your watchlist is empty. Add a ticker from any stock page to track it here.</p>
            ) : (
              <>
                <p className="support-text">
                  {items.length} ticker{items.length === 1 ? '' : 's'} tracked.
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {items.slice(0, PREVIEW_LIMIT).map((item) => (
                    <Link
                      key={item.ticker}
                      to={paths.stock(item.ticker)}
                      className="badge bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]"
                    >
                      {item.ticker}
                    </Link>
                  ))}
                </div>
              </>
            )
          }
        </AsyncSection>
      )}
    </section>
  )
}
