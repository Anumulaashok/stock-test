import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useAsync } from '../../hooks/useAsync'
import { AsyncSection } from '../../components/ui/AsyncSection'
import { SkeletonRows } from '../../components/ui/Skeleton'
import { fetchWatchlistEnriched } from '../../api/portfolio'
import { paths } from '../../routes/paths'
import { formatCurrency, formatSignedPercent, toDisplayNumber } from '../../lib/format'
import { toneFromBand, TONE_CLASS } from '../../lib/signals'
import type { ScoreBand, WatchlistItemEnriched } from '../../types/backend'

const PREVIEW_LIMIT = 8

function changeToneClass(changePercent: string | null): string {
  if (changePercent === null) return 'text-[var(--color-text-faint)]'
  return Number(changePercent) >= 0
    ? 'text-[var(--color-status-positive)]'
    : 'text-[var(--color-status-negative)]'
}

function WatchlistRow({ item }: { item: WatchlistItemEnriched }) {
  const scoreTone = toneFromBand((item.band as ScoreBand | null) ?? null)
  return (
    <Link
      to={paths.stock(item.ticker)}
      className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-3 rounded-[var(--radius-sm)] px-2 py-1.5 text-[12.5px] hover:bg-[var(--color-surface-raised)]"
    >
      <span className="truncate font-semibold">{item.ticker}</span>
      <span className="font-mono-nums text-right">{formatCurrency(item.current_price) ?? '—'}</span>
      <span className={`font-mono-nums text-right ${changeToneClass(item.change_percent)}`}>
        {formatSignedPercent(item.change_percent) ?? '—'}
      </span>
      <span className={`font-mono-nums text-right font-semibold ${TONE_CLASS[scoreTone]}`}>
        {toDisplayNumber(item.overall_score, 0) ?? '—'}
      </span>
    </Link>
  )
}

/** Real watchlist prices/changes/scores from `GET
 * /api/v1/watchlist/enriched` -- shows a graceful signed-out state
 * instead of disappearing or crashing when the viewer is anonymous. */
export function WatchlistSummary() {
  const { status } = useAuth()
  const state = useAsync(fetchWatchlistEnriched, [], { enabled: status === 'authenticated' })

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
              <div className="flex flex-col">
                <div className="grid grid-cols-[1fr_auto_auto_auto] gap-3 px-2 pb-1 text-[9.5px] font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
                  <span>Stock</span>
                  <span className="text-right">Price</span>
                  <span className="text-right">Change</span>
                  <span className="text-right">Score</span>
                </div>
                <div className="flex flex-col divide-y divide-[var(--color-border)]">
                  {items.slice(0, PREVIEW_LIMIT).map((item) => (
                    <WatchlistRow key={item.ticker} item={item} />
                  ))}
                </div>
              </div>
            )
          }
        </AsyncSection>
      )}
    </section>
  )
}
