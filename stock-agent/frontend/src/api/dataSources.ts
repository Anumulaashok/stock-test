import { getJson } from './client'
import type { DataSourceStatusResponse } from '../types/backend'

/**
 * Live status of every configured data source: what each is capable of,
 * which categories it owns, and whether it is currently working.
 * See app/api/market.py.
 */
export async function fetchDataSourceStatus(): Promise<DataSourceStatusResponse> {
  return getJson<DataSourceStatusResponse>('/api/v1/market/data-sources/status')
}
