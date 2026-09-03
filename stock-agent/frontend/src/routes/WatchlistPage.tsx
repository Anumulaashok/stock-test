import { addWatchlistItem, fetchWatchlist, removeWatchlistItem } from '../api/portfolio'
import { AsyncSection } from '../components/ui/AsyncSection'
import { AddTickerForm } from '../features/watchlist/AddTickerForm'
import { WatchlistList } from '../features/watchlist/WatchlistList'
import { useAsync } from '../hooks/useAsync'

/**
 * Extracted from `DashboardPage.tsx`'s inlined `WatchlistTable` +
 * `AddWatchlistForm`. `WatchlistItem` is just `{ ticker, created_at }` --
 * no price/score/delta exists on `GET /api/v1/watchlist` today, so this
 * page only ever renders what the backend actually returns.
 */
export function WatchlistPage() {
  const watchlist = useAsync(fetchWatchlist, [])

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
