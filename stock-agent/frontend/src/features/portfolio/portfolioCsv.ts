import { toCsv } from '../../lib/csv'
import type { HoldingWithMarketData } from '../../types/backend'

const HEADERS = [
  'ticker',
  'quantity',
  'average_cost',
  'current_price',
  'price_status',
  'market_value',
  'unrealized_gain',
  'unrealized_gain_percent',
]

/** Reshapes already-fetched holdings into CSV text -- every field here
 * is a value the backend returned, none computed. */
export function holdingsToCsv(holdings: HoldingWithMarketData[]): string {
  return toCsv(
    HEADERS,
    holdings.map((h) => [
      h.ticker,
      h.quantity,
      h.average_cost,
      h.current_price,
      h.price_status,
      h.market_value,
      h.unrealized_gain,
      h.unrealized_gain_percent,
    ]),
  )
}
