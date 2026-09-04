import { addWatchlistItem, fetchWatchlistEnriched, removeWatchlistItem } from '../api/portfolio'
import { AsyncSection } from '../components/ui/AsyncSection'
import { AddTickerForm } from '../features/watchlist/AddTickerForm'
import { WatchlistList } from '../features/watchlist/WatchlistList'
import { useAsync } from '../hooks/useAsync'

/**
 * Extracted from `DashboardPage.tsx`'s inlined `WatchlistTable` +
 * `AddWatchlistForm`, now backed by `GET /api/v1/watchlist/enriched`
 * (price + latest research score per ticker) instead of the bare
 * `{ ticker, created_at }` `GET /api/v1/watchlist` returns -- both
 * halves render "Unavailable"/blank, never a fabricated value, when a
 * ticker has no quote or has never been researched.
 */
export function WatchlistPage() {
  const watchlist = useAsync(fetchWatchlistEnriched, [])

  async function handleAdd(ticker: string) {
    await addWatchlistItem(ticker)
    watchlist.reload()
  }

  async function handleRemove(ticker: string) {
    await removeWatchlistItem(ticker)
    watchlist.reload()
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 pb-32 pt-8 sm:pb-36">
      <div>
        <h1 className="text-xl font-semibold">Watchlist</h1>
        <p className="support-text">Tickers you're tracking -- add one below to keep it here for quick access.</p>
      </div>

      <AddTickerForm onAdd={handleAdd} />

      <AsyncSection state={watchlist} onRetry={watchlist.reload} errorTitle="Could not load your watchlist">
        {(items) => <WatchlistList items={items} onRemove={handleRemove} />}
      </AsyncSection>
    </main>
  )
}
