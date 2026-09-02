import { getJson } from './client'

export interface StockSearchResult {
  symbol: string
  name: string
  exchange: string
  isin: string | null
}

/**
 * Ticker/company-name suggestions for the search bar. Served from a
 * local, static NSE equity list on the backend -- fast, no external
 * API key involved, safe to call on every keystroke.
 */
export async function searchStocks(query: string): Promise<StockSearchResult[]> {
  const trimmed = query.trim()
  if (!trimmed) return []
  const params = new URLSearchParams({ q: trimmed, limit: '8' })
  return getJson<StockSearchResult[]>(`/api/v1/search?${params.toString()}`, 10_000)
}
