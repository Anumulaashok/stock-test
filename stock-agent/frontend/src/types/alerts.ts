/** Mirrors `app/models/alerts.py`. Alerts evaluate on read (D6/D10) --
 * there is no scheduler; `POST /alerts/evaluate` is the only place a
 * condition is ever checked, and only when a caller asks for it. */

export type AlertConditionType =
  | 'PRICE_ABOVE'
  | 'PRICE_BELOW'
  | 'SCORE_ABOVE'
  | 'SCORE_BELOW'
  | 'DMA_CROSSOVER_GOLDEN'
  | 'DMA_CROSSOVER_DEATH'
  | 'REGIME_CHANGE'

export const THRESHOLD_CONDITIONS: readonly AlertConditionType[] = ['PRICE_ABOVE', 'PRICE_BELOW', 'SCORE_ABOVE', 'SCORE_BELOW']

export interface AlertCreateRequest {
  ticker: string
  condition_type: AlertConditionType
  threshold_value?: string | null
}

export interface Alert {
  id: string
  ticker: string
  condition_type: AlertConditionType
  threshold_value: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AlertTrigger {
  id: string
  alert_id: string
  ticker: string
  condition_type: AlertConditionType
  triggered_at: string
  observed_value: string
  acknowledged: boolean
}

/** `status` is `"met" | "not_met" | "unavailable"` -- "unavailable"
 * (the data this condition needs couldn't be read right now) is never
 * collapsed into "not_met"; they mean different things to a user. */
export interface AlertEvaluation {
  alert_id: string
  ticker: string
  condition_type: AlertConditionType
  status: 'met' | 'not_met' | 'unavailable'
  observed_value: string | null
  newly_triggered: boolean
}

export interface AlertEvaluationResponse {
  checked_at: string
  evaluations: AlertEvaluation[]
}
