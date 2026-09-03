import { deleteJson, getJson, postJson, putJson } from './client'
import type {
  CompanySearchResponse,
  ForecastAccuracySummary,
  IndexQuotesResponse,
  ScreenerCompanyListImportResult,
  ScreenerCookieStatus,
  ScreenerImportRequest,
  ScreenerImportResult,
  ScreenerMappingSummary,
} from '../types/backend'

/**
 * Triggers a one-time historical bulk import from Screener.in for
 * `ticker`. `screener_company_id` may be omitted once a mapping is
 * already registered for the ticker (see `registerScreenerCompanyMappings`).
 * See app/api/market.py.
 */
export async function importHistoricalPrices(
  ticker: string,
  request: ScreenerImportRequest,
): Promise<ScreenerImportResult> {
  return postJson<ScreenerImportResult>(
    `/api/v1/market/${encodeURIComponent(ticker.trim().toUpperCase())}/historical/import`,
    request,
  )
}

export async function fetchForecastAccuracy(ticker: string): Promise<ForecastAccuracySummary> {
  return getJson<ForecastAccuracySummary>(`/api/v1/market/${encodeURIComponent(ticker.trim().toUpperCase())}/forecast-accuracy`)
}

/**
 * Bulk-registers ticker -> Screener-company-id mappings by pasting one
 * of Screener's own company-search JSON results (a plain array of
 * `{id, name, url}` objects) verbatim.
 */
export async function registerScreenerCompanyMappings(companies: unknown[]): Promise<ScreenerCompanyListImportResult> {
  return postJson<ScreenerCompanyListImportResult>('/api/v1/market/screener-mappings/import', { companies })
}

export async function searchScreenerCompanyMappings(query: string, limit = 8): Promise<ScreenerMappingSummary[]> {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  return getJson<ScreenerMappingSummary[]>(`/api/v1/market/screener-mappings?${params}`)
}

/**
 * Company-name search for the ticker-input autocomplete. Uses Screener's
 * own live search (auto-registering results as mappings) when
 * SCREENER_SESSION_COOKIE is configured server-side, otherwise falls
 * back to the local static NSE directory -- `response.source` always
 * says which one actually answered.
 */
export async function searchCompanies(query: string): Promise<CompanySearchResponse> {
  const params = new URLSearchParams({ q: query })
  return getJson<CompanySearchResponse>(`/api/v1/market/company-search?${params}`)
}

export async function fetchScreenerCookieStatus(): Promise<ScreenerCookieStatus> {
  return getJson<ScreenerCookieStatus>('/api/v1/market/settings/screener-cookie')
}

export async function setScreenerCookie(sessionCookie: string): Promise<ScreenerCookieStatus> {
  return putJson<ScreenerCookieStatus>('/api/v1/market/settings/screener-cookie', { session_cookie: sessionCookie })
}

export async function clearScreenerCookie(): Promise<ScreenerCookieStatus> {
  return deleteJson<ScreenerCookieStatus>('/api/v1/market/settings/screener-cookie')
}

/** Real Nifty 50 / Sensex levels via the configured MarketDataProvider
 * (yfinance's ^NSEI/^BSESN symbols) -- never fabricated; a provider
 * failure reports status="unavailable" per index instead. */
export async function fetchIndexQuotes(): Promise<IndexQuotesResponse> {
  return getJson<IndexQuotesResponse>('/api/v1/market/indices')
}
