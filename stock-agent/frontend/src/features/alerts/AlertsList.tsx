import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { friendlyErrorMessage } from '../../components/ui/ErrorState'
import { paths } from '../../routes/paths'
import { formatDate } from '../../lib/format'
import { CONDITION_LABEL } from './conditionLabels'
import type { Alert, AlertEvaluation } from '../../types/alerts'

const STATUS_LABEL: Record<AlertEvaluation['status'], string> = {
  met: 'Condition met',
  not_met: 'Condition not met',
  unavailable: 'Data unavailable',
}

const STATUS_CLASS: Record<AlertEvaluation['status'], string> = {
  met: 'text-[var(--color-accent-strong)] bg-[var(--color-accent-soft)]',
  not_met: 'text-[var(--color-text-faint)] bg-[var(--color-border)]',
  unavailable: 'text-[var(--color-text-faint)] bg-[var(--color-border)]',
}

function EvaluationBadge({ evaluation }: { evaluation: AlertEvaluation | undefined }) {
  if (!evaluation) return null
  return (
    <span className={`inline-flex flex-col gap-0.5 rounded-md px-2 py-1 text-right text-xs ${STATUS_CLASS[evaluation.status]}`}>
      <span className="font-semibold">{STATUS_LABEL[evaluation.status]}</span>
      {evaluation.observed_value !== null && <span className="font-mono-nums text-[10px]">observed: {evaluation.observed_value}</span>}
    </span>
  )
}

function AlertRow({
  alert,
  evaluation,
  onToggleActive,
  onDelete,
}: {
  alert: Alert
  evaluation: AlertEvaluation | undefined
  onToggleActive: (alert: Alert) => Promise<void>
  onDelete: (alert: Alert) => Promise<void>
}) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleToggle() {
    setBusy(true)
    setError(null)
    try {
      await onToggleActive(alert)
    } catch (err) {
      setError(err instanceof ApiError ? friendlyErrorMessage(err) : 'Could not update this alert.')
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    setBusy(true)
    setError(null)
    try {
      await onDelete(alert)
    } catch (err) {
      setError(err instanceof ApiError ? friendlyErrorMessage(err) : 'Could not remove this alert.')
      setBusy(false)
      setConfirming(false)
    }
  }

  return (
    <li className="surface-card flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-0.5">
        <Link to={paths.stock(alert.ticker)} className="font-mono-nums text-sm font-semibold text-[var(--color-accent-strong)] hover:underline">
          {alert.ticker}
        </Link>
        <span className="support-text text-xs">
          {CONDITION_LABEL[alert.condition_type]}
          {alert.threshold_value !== null && ` ${alert.threshold_value}`}
        </span>
        <span className="support-text text-xs">Added {formatDate(alert.created_at) ?? '—'}</span>
      </div>

      <div className="flex items-center gap-3">
        <EvaluationBadge evaluation={evaluation} />
        <label className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)]">
          <input
            type="checkbox"
            checked={alert.is_active}
            disabled={busy}
            onChange={handleToggle}
            className="h-3.5 w-3.5 rounded border-[var(--color-border-strong)] accent-[var(--color-accent)]"
          />
          Active
        </label>

        {confirming ? (
          <>
            <span className="text-xs text-[var(--color-status-negative)]">Remove?</span>
            <button
              type="button"
              onClick={handleDelete}
              disabled={busy}
              className="rounded-[var(--radius-sm)] border border-[var(--color-status-negative)]/50 bg-[var(--color-status-negative)]/10 px-2.5 py-1 text-xs font-medium text-[var(--color-status-negative)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              Confirm
            </button>
            <button type="button" onClick={() => setConfirming(false)} disabled={busy} className="text-xs text-[var(--color-text-faint)] underline">
              Cancel
            </button>
          </>
        ) : (
          <button type="button" onClick={() => setConfirming(true)} className="text-xs text-[var(--color-status-negative)] underline">
            Remove
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="text-xs text-[var(--color-status-negative)] sm:basis-full">
          {error}
        </p>
      )}
    </li>
  )
}

export function AlertsList({
  alerts,
  evaluations,
  onToggleActive,
  onDelete,
}: {
  alerts: Alert[]
  evaluations: Map<string, AlertEvaluation>
  onToggleActive: (alert: Alert) => Promise<void>
  onDelete: (alert: Alert) => Promise<void>
}) {
  if (alerts.length === 0) {
    return (
      <div className="surface-card flex flex-col items-center gap-1 p-8 text-center">
        <p className="card-heading">No alerts yet</p>
        <p className="support-text">Add one above to get notified when a ticker meets a condition.</p>
      </div>
    )
  }

  return (
    <ul className="flex flex-col gap-2">
      {alerts.map((alert) => (
        <AlertRow key={alert.id} alert={alert} evaluation={evaluations.get(alert.id)} onToggleActive={onToggleActive} onDelete={onDelete} />
      ))}
    </ul>
  )
}
