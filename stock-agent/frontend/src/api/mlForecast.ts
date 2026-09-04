import { getJson } from './client'
import type { MlForecastResult } from '../types/mlForecast'

export async function fetchMlForecast(ticker: string): Promise<MlForecastResult> {
  return getJson<MlForecastResult>(`/api/v1/ml-forecast/${encodeURIComponent(ticker.trim().toUpperCase())}`)
}
