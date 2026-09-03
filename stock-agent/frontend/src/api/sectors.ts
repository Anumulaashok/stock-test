import { getJson } from './client'
import type { MarketOpportunityResult } from '../types/backend'

export async function fetchMarketOpportunity(forceRefresh = false): Promise<MarketOpportunityResult> {
  const query = forceRefresh ? '?force_refresh=true' : ''
  return getJson<MarketOpportunityResult>(`/api/v1/sectors${query}`)
}
