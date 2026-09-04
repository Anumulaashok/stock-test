import { getJson } from './client'
import { searchCompanies } from './marketHistory'

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

/**
 * `searchStocks`, falling back to `GET /api/v1/market/company-search`
 * (Screener's own live search) only when the local list finds nothing --
 * that endpoint auto-registers a Screener-id mapping for every result on
 * every call (see `app/api/market.py::search_companies`), so it is
 * deliberately not the first thing hit on every keystroke. The fallback
 * covers exactly the case the local static NSE list misses: a newly
 * listed company, a name spelled differently than NSE's own listing, or
 * anything the (necessarily stale) bundled CSV doesn't have yet.
 * Screener-sourced results are labeled "Screener" rather than "NSE" --
 * this app doesn't actually know the exchange for those, and the local
 * list's "NSE" label is only accurate because that dataset genuinely is
 * NSE-only.
 */
export async function searchStocksWithScreenerFallback(query: string): Promise<StockSearchResult[]> {
  const local = await searchStocks(query)
  if (local.length > 0) return local

  const trimmed = query.trim()
  if (!trimmed) return []
  try {
    const response = await searchCompanies(trimmed)
    if (response.source !== 'screener') return [] // already the local list, and it was empty
    return response.results.map((r) => ({
      symbol: r.ticker,
      name: r.company_name ?? r.ticker,
      exchange: 'Screener',
      isin: null,
    }))
  } catch {
    // A failed fallback should never break the primary (already-empty)
    // suggestion list -- the user still sees "no matches", not an error.
    return []
  }
}
