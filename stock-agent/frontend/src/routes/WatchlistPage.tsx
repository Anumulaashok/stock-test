import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { addWatchlistItem, fetchWatchlistEnriched, removeWatchlistItem } from '../api/portfolio'
import { AsyncSection } from '../components/ui/AsyncSection'
import { AddTickerForm } from '../features/watchlist/AddTickerForm'
import { WatchlistList } from '../features/watchlist/WatchlistList'
import { watchlistToCsv } from '../features/watchlist/watchlistCsv'
import { useAsync } from '../hooks/useAsync'
import { downloadCsv } from '../lib/csv'
import { paths } from './paths'

const MAX_COMPARE = 4

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
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([])
  const navigate = useNavigate()

  async function handleAdd(ticker: string) {
    await addWatchlistItem(ticker)
    watchlist.reload()
  }

  async function handleRemove(ticker: string) {
    await removeWatchlistItem(ticker)
    watchlist.reload()
  }

  function toggleCompare(ticker: string) {
    setSelectedForCompare((prev) => {
      if (prev.includes(ticker)) return prev.filter((t) => t !== ticker)
      if (prev.length >= MAX_COMPARE) return prev
      return [...prev, ticker]
    })
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 pb-32 pt-8 sm:pb-36">
      <div>
        <h1 className="text-xl font-semibold">Watchlist</h1>
        <p className="support-text">Tickers you're tracking -- add one below to keep it here for quick access.</p>
      </div>

      <AddTickerForm onAdd={handleAdd} />

      <AsyncSection state={watchlist} onRetry={watchlist.reload} errorTitle="Could not load your watchlist">
        {(items) => (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-end gap-2">
              <span className="support-text text-xs">
                {selectedForCompare.length > 0 ? `${selectedForCompare.length}/${MAX_COMPARE} selected to compare` : 'Select tickers to compare'}
              </span>
              <button
                type="button"
                onClick={() => navigate(paths.compare(selectedForCompare))}
                disabled={selectedForCompare.length < 2}
                className="btn-secondary px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-60"
              >
                Compare selected
              </button>
              <button
                type="button"
                onClick={() => downloadCsv('watchlist', watchlistToCsv(items))}
                disabled={items.length === 0}
                className="btn-secondary px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-60"
              >
                Export CSV
              </button>
            </div>
            <WatchlistList items={items} onRemove={handleRemove} selectedForCompare={selectedForCompare} onToggleCompare={toggleCompare} />
          </div>
        )}
      </AsyncSection>
    </main>
  )
}
