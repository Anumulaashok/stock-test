import { toCsv } from '../../lib/csv'
import type { WatchlistItemEnriched } from '../../types/backend'

const HEADERS = [
  'ticker',
  'added_at',
  'current_price',
  'change_percent',
  'overall_score',
  'band',
  'price_status',
  'last_researched_at',
]

/** Reshapes already-fetched watchlist rows into CSV text -- every field
 * here is a value the backend returned, none computed. */
export function watchlistToCsv(items: WatchlistItemEnriched[]): string {
  return toCsv(
    HEADERS,
    items.map((item) => [
      item.ticker,
      item.created_at,
      item.current_price,
      item.change_percent,
      item.overall_score,
      item.band,
      item.price_status,
      item.last_researched_at,
    ]),
  )
}
