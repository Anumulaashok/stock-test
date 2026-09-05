import { useEffect, useState } from 'react'
import { createAlert, deleteAlert, evaluateAlerts, fetchAlerts, setAlertActive } from '../api/alerts'
import { AsyncSection } from '../components/ui/AsyncSection'
import { AddAlertForm } from '../features/alerts/AddAlertForm'
import { AlertsList } from '../features/alerts/AlertsList'
import { useAsync } from '../hooks/useAsync'
import { formatDateTime } from '../lib/format'
import type { Alert, AlertEvaluation } from '../types/alerts'

/**
 * Alerts evaluate on read (D6/D10) -- there is no background monitoring
 * or push. This page checks every active alert once when it's opened,
 * and again only if you click "Check now." Closing the tab means
 * nothing is being watched until you come back.
 */
export function AlertsPage() {
  const state = useAsync(fetchAlerts, [])
  const [evaluations, setEvaluations] = useState<Map<string, AlertEvaluation>>(new Map())
  const [checkedAt, setCheckedAt] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)

  async function runCheck() {
    setChecking(true)
    try {
      const response = await evaluateAlerts()
      setEvaluations(new Map(response.evaluations.map((e) => [e.alert_id, e])))
      setCheckedAt(response.checked_at)
    } finally {
      setChecking(false)
    }
  }

  useEffect(() => {
    void runCheck()
    // Only ever on mount -- this is the one honest "checked when the
    // app is open" moment; nothing here re-runs on a timer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleAdd(request: Parameters<typeof createAlert>[0]) {
    await createAlert(request)
    state.reload()
  }

  async function handleToggleActive(alert: Alert) {
    await setAlertActive(alert.id, !alert.is_active)
    state.reload()
  }

  async function handleDelete(alert: Alert) {
    await deleteAlert(alert.id)
    state.reload()
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 pb-32 pt-8 sm:pb-36">
      <div>
        <h1 className="text-xl font-semibold">Alerts</h1>
        <p className="support-text">
          Checked just now, when this page opened -- not continuously in the background. Click "Check now" to
          re-check.
        </p>
      </div>

      <AddAlertForm onAdd={handleAdd} />

      <div className="flex items-center justify-between gap-2">
        <span className="support-text text-xs">
          {checking ? 'Checking…' : checkedAt ? `Last checked ${formatDateTime(checkedAt) ?? checkedAt}` : 'Not checked yet'}
        </span>
        <button type="button" onClick={() => void runCheck()} disabled={checking} className="btn-secondary px-3 py-1.5 text-xs">
          {checking ? 'Checking…' : 'Check now'}
        </button>
      </div>

      <AsyncSection state={state} onRetry={state.reload} errorTitle="Could not load your alerts">
        {(alerts) => (
          <AlertsList alerts={alerts} evaluations={evaluations} onToggleActive={handleToggleActive} onDelete={handleDelete} />
        )}
      </AsyncSection>
    </main>
  )
}
