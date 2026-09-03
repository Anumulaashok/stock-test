import { useEffect, useState } from 'react'
import { addWatchlistItem, fetchWatchlist, removeWatchlistItem } from '../api/portfolio'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'

/** Whether `ticker` is on the signed-in user's watchlist, plus a toggle
 * action -- extracted from `AnalysisPage` so `StockLayout` (and any other
 * ticker-scoped chrome) can share it without prop drilling. `null` means
 * "not yet known" (still loading, or not authenticated), never a guessed
 * default. */
export function useWatchlistMembership(ticker: string) {
  const { status: authStatus } = useAuth()
  const [inWatchlist, setInWatchlist] = useState<boolean | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (authStatus !== 'authenticated') {
      setInWatchlist(null)
      return
    }
    let cancelled = false
    fetchWatchlist()
      .then((items) => {
        if (cancelled) return
        setInWatchlist(items.some((item) => item.ticker.toUpperCase() === ticker.toUpperCase()))
      })
      .catch(() => {
        if (!cancelled) setInWatchlist(null)
      })
    return () => {
      cancelled = true
    }
  }, [authStatus, ticker])

  async function toggle() {
    if (inWatchlist === null) return
    setPending(true)
    setError(null)
    const wasInWatchlist = inWatchlist
    try {
      if (wasInWatchlist) {
        await removeWatchlistItem(ticker)
      } else {
        await addWatchlistItem(ticker)
      }
      setInWatchlist(!wasInWatchlist)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update your watchlist.')
    } finally {
      setPending(false)
    }
  }

  return { authStatus, inWatchlist, pending, error, toggle }
}
