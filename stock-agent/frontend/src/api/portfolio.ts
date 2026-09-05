import { deleteRequest, getJson, patchJson, postJson } from './client'
import type { Holding, PortfolioSummary, WatchlistItem, WatchlistItemEnriched } from '../types/backend'

export async function fetchHoldings(): Promise<Holding[]> {
  return getJson<Holding[]>('/api/v1/portfolio')
}

export async function fetchPortfolioSummary(): Promise<PortfolioSummary> {
  return getJson<PortfolioSummary>('/api/v1/portfolio/summary')
}

export async function addHolding(ticker: string, quantity: string, averageCost: string): Promise<Holding> {
  return postJson<Holding>('/api/v1/portfolio/holdings', {
    ticker: ticker.trim().toUpperCase(),
    quantity,
    average_cost: averageCost,
  })
}

export async function updateHolding(
  holdingId: string,
  updates: { quantity?: string; average_cost?: string },
): Promise<Holding> {
  return patchJson<Holding>(`/api/v1/portfolio/holdings/${holdingId}`, updates)
}

export async function deleteHolding(holdingId: string): Promise<void> {
  await deleteRequest(`/api/v1/portfolio/holdings/${holdingId}`)
}

export async function fetchWatchlist(): Promise<WatchlistItem[]> {
  return getJson<WatchlistItem[]>('/api/v1/watchlist')
}

/** `fetchWatchlist` plus a live quote and the latest research score per
 * ticker -- for the Watchlist page's table. Prefer plain `fetchWatchlist`
 * when only ticker membership/count is needed (e.g. Home's summary
 * card), since this does real per-ticker work on the backend. */
export async function fetchWatchlistEnriched(): Promise<WatchlistItemEnriched[]> {
  return getJson<WatchlistItemEnriched[]>('/api/v1/watchlist/enriched')
}

export async function addWatchlistItem(ticker: string): Promise<WatchlistItem> {
  return postJson<WatchlistItem>('/api/v1/watchlist', { ticker: ticker.trim().toUpperCase() })
}

export async function removeWatchlistItem(ticker: string): Promise<void> {
  await deleteRequest(`/api/v1/watchlist/${encodeURIComponent(ticker)}`)
}
