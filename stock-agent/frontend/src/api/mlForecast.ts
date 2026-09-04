import { getJson } from './client'
import type { MlForecastAccuracyResponse, MlForecastHistoryResponse, MlForecastResult, MlHorizonKey } from '../types/mlForecast'

function base(ticker: string): string {
  return `/api/v1/ml-forecast/${encodeURIComponent(ticker.trim().toUpperCase())}`
}

export async function fetchMlForecast(ticker: string): Promise<MlForecastResult> {
  return getJson<MlForecastResult>(base(ticker))
}

/** Requires `horizon`, deliberately -- `app/forecasting/ml/persistence.py`
 * orders by `prediction_timestamp desc` and applies `limit` BEFORE any
 * horizon grouping when `horizon` is omitted, so an unfiltered call with
 * `limit=200` can silently starve a horizon that predicts less often
 * than the others. Filtering server-side by horizon avoids the bias
 * entirely rather than disclosing it. `limit` caps at 200 server-side. */
export async function fetchMlForecastHistory(
  ticker: string,
  horizon: MlHorizonKey,
  limit = 200,
): Promise<MlForecastHistoryResponse> {
  return getJson<MlForecastHistoryResponse>(`${base(ticker)}/history?horizon=${horizon}&limit=${limit}`)
}

export async function fetchMlForecastAccuracy(ticker: string): Promise<MlForecastAccuracyResponse> {
  return getJson<MlForecastAccuracyResponse>(`${base(ticker)}/accuracy`)
}
