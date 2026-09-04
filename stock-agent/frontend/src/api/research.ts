import { ApiError, getJson, postJson } from './client'
import type { RecentResearchEntry, ResearchRunResult, ResearchRunSummary } from '../types/backend'

/**
 * Runs (or reuses) today's research snapshot for `ticker`. Normal calls
 * reuse an already-completed snapshot for today when one exists --
 * `forceRefresh` always computes and saves a new one. This replaces
 * `analyzeTicker` (`./analysis.ts`) as the dashboard's entry point; that
 * function is kept for callers that intentionally want the
 * never-persisted, always-fresh compute path.
 */
export async function runResearch(ticker: string, forceRefresh = false): Promise<ResearchRunResult> {
  return postJson<ResearchRunResult>('/api/v1/research/ticker', {
    ticker: ticker.trim().toUpperCase(),
    force_refresh: forceRefresh,
    include_price_trend_forecast: true,
  })
}

/**
 * Reads the latest already-completed research run for `ticker` (any
 * date, normal or force-refresh) without triggering any new
 * computation -- `GET /api/v1/research/{ticker}`. Returns `null` when
 * nothing has ever been researched for this ticker (404), so callers
 * can fall back to `runResearch` for a first-time compute. Used so a
 * plain search always surfaces the newest computed result instead of
 * silently kicking off a redundant "today's normal run".
 */
export async function fetchLatestResearch(ticker: string): Promise<ResearchRunResult | null> {
  try {
    return await getJson<ResearchRunResult>(`/api/v1/research/${encodeURIComponent(ticker.trim().toUpperCase())}`)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

/**
 * The latest saved run for every ticker ever researched, newest first --
 * global, not scoped to any watchlist (research has no `user_id`). Backs
 * Intelligence home's "Recent Research" and the `/research` history
 * page; replaces the "fetch the watchlist, then one request per ticker"
 * fan-out those pages previously would have needed.
 */
export async function fetchRecentResearch(limit = 20, offset = 0): Promise<RecentResearchEntry[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  return getJson<RecentResearchEntry[]>(`/api/v1/research/recent?${params}`)
}

export async function fetchResearchHistory(ticker: string, limit = 20): Promise<ResearchRunSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  return getJson<ResearchRunSummary[]>(
    `/api/v1/research/${encodeURIComponent(ticker.trim().toUpperCase())}/history?${params}`,
  )
}

/** Loads the EXACT saved report for a past run -- never recomputes it. */
export async function fetchResearchRun(ticker: string, researchRunId: string): Promise<ResearchRunResult> {
  return getJson<ResearchRunResult>(
    `/api/v1/research/${encodeURIComponent(ticker.trim().toUpperCase())}/history/${encodeURIComponent(researchRunId)}`,
  )
}
