/** Mirrors `app/models/ml_forecast.py` -- the ML multi-horizon
 * forecasting subsystem's response shape. Kept separate from the
 * existing `ReportForecastSection` types in `backend.ts` since this is
 * a parallel system (see `app.forecasting.ml`), not a replacement. */

export type MlHorizonKey = '14D' | '1M' | '3M' | '1Y'

export interface QuantileEstimate {
  p10: number | null
  p25: number | null
  p50: number | null
  p75: number | null
  p90: number | null
}

export interface ModelAgreementEntry {
  model_name: string
  point_return: number
  weight: number
}

export interface AnalogSummary {
  sample_size: number
  is_reliable: boolean
  positive_rate: number | null
  negative_rate: number | null
  mean_return: number | null
  median_return: number | null
  quantiles: QuantileEstimate | null
}

export interface HistoricalAccuracy {
  sample_size: number
  mae: number | null
  rmse: number | null
  directional_accuracy: number | null
  brier_score: number | null
  interval_coverage_80: number | null
}

export interface ForecastDriversResponse {
  positive_drivers: string[]
  negative_drivers: string[]
}

export interface MlHorizonForecast {
  horizon: MlHorizonKey
  target_date: string
  current_price: number
  expected_return: number
  expected_price: number
  quantiles: QuantileEstimate
  probability_positive: number
  forecast_quality: 'HIGH' | 'MEDIUM' | 'LOW'
  quality_score: number
  quality_reasons: string[]
  model_agreement: number
  model_outputs: ModelAgreementEntry[]
  drivers: ForecastDriversResponse
  analog: AnalogSummary
  historical_accuracy: HistoricalAccuracy | null
}

export interface NewsImpactEventSummary {
  event_type: string
  sample_size: number
  is_reliable: boolean
  median_return_5d: number | null
  median_return_14d: number | null
  positive_rate_5d: number | null
  positive_rate_14d: number | null
}

export interface RecentNewsItem {
  headline: string
  published_at: string
  event_type: string
  sentiment: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'
  market_timing: string
  url: string | null
}

export interface NewsImpactSection {
  recent_events: RecentNewsItem[]
  historical_statistics: NewsImpactEventSummary[]
  data_available: boolean
  note: string | null
}

export interface DataQuality {
  price_history_days: number
  fundamentals_available: boolean
  news_available: boolean
  regime: string
  training_data_end_date: string | null
}

/** Mirrors `GET /api/v1/ml-forecast/{ticker}/history`'s per-prediction
 * row (`app/api/ml_forecast.py`). `actual_return`/`actual_price` are
 * `null` until the horizon's target date elapses -- that is the PENDING
 * state, never a zero, and must be treated as absent everywhere. */
export interface MlForecastPrediction {
  prediction_timestamp: string
  horizon: MlHorizonKey
  predicted_return: number
  predicted_price: number
  target_date: string
  actual_return: number | null
  actual_price: number | null
  direction_correct: boolean | null
  forecast_quality: string
  model_version: string
}

export interface MlForecastHistoryResponse {
  ticker: string
  predictions: MlForecastPrediction[]
}

/** One horizon's entry in `GET .../accuracy`'s `accuracy_by_horizon`.
 * `sample_size: 0` is a distinct, real response shape (no walk-forward
 * evaluation recorded yet) -- never render it as a 0% accuracy figure. */
export interface MlAccuracyHorizonStats {
  sample_size: number
  mae: number | null
  rmse: number | null
  directional_accuracy: number | null
  brier_score: number | null
  interval_coverage_80: number | null
  note?: string
}

export type MlAccuracyByHorizon = Partial<Record<MlHorizonKey, MlAccuracyHorizonStats>>

export interface MlForecastAccuracyResponse {
  ticker: string
  accuracy_by_horizon: MlAccuracyByHorizon
}

export interface MlForecastResult {
  ticker: string
  generated_at: string
  data_date: string | null
  current_price: number
  regime: string
  horizons: Record<MlHorizonKey, MlHorizonForecast>
  news_impact: NewsImpactSection
  data_quality: DataQuality
  model_version: string
  feature_version: string
  news_model_version: string
  warnings: string[]
}
