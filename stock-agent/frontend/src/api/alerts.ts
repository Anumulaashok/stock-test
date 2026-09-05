import { deleteRequest, getJson, patchJson, postJson } from './client'
import type { Alert, AlertCreateRequest, AlertEvaluationResponse, AlertTrigger } from '../types/alerts'

export async function fetchAlerts(): Promise<Alert[]> {
  return getJson<Alert[]>('/api/v1/alerts')
}

export async function createAlert(request: AlertCreateRequest): Promise<Alert> {
  return postJson<Alert>('/api/v1/alerts', { ...request, ticker: request.ticker.trim().toUpperCase() })
}

export async function setAlertActive(alertId: string, isActive: boolean): Promise<Alert> {
  return patchJson<Alert>(`/api/v1/alerts/${alertId}`, { is_active: isActive })
}

export async function deleteAlert(alertId: string): Promise<void> {
  await deleteRequest(`/api/v1/alerts/${alertId}`)
}

/**
 * Checks every active alert's condition right now -- the only place
 * this ever happens (D6/D10). Call this only when the user opens the
 * Alerts page (or explicitly asks to re-check), never on a timer or on
 * every route change: some conditions read a live quote, which is a
 * real (if cheap, unmetered-for-Indian-tickers-via-the-configured-
 * provider) per-alert cost, not a free background poll.
 */
export async function evaluateAlerts(): Promise<AlertEvaluationResponse> {
  return postJson<AlertEvaluationResponse>('/api/v1/alerts/evaluate', {})
}

/** Cheap -- a DB-only read of already-recorded triggers, no live quote
 * calls. Safe to call on app load (e.g. for a header unread count). */
export async function fetchAlertTriggers(unacknowledgedOnly = false): Promise<AlertTrigger[]> {
  const params = unacknowledgedOnly ? '?unacknowledged_only=true' : ''
  return getJson<AlertTrigger[]>(`/api/v1/alerts/triggers${params}`)
}

export async function acknowledgeAlertTrigger(triggerId: string): Promise<void> {
  await postJson(`/api/v1/alerts/triggers/${triggerId}/acknowledge`, {})
}
