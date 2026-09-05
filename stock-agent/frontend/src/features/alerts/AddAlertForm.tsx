import { useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { friendlyErrorMessage } from '../../components/ui/ErrorState'
import { CONDITION_LABEL, CONDITION_ORDER } from './conditionLabels'
import { THRESHOLD_CONDITIONS, type AlertConditionType, type AlertCreateRequest } from '../../types/alerts'

export function AddAlertForm({ onAdd }: { onAdd: (request: AlertCreateRequest) => Promise<void> }) {
  const [ticker, setTicker] = useState('')
  const [conditionType, setConditionType] = useState<AlertConditionType>('PRICE_ABOVE')
  const [threshold, setThreshold] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const needsThreshold = THRESHOLD_CONDITIONS.includes(conditionType)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmedTicker = ticker.trim().toUpperCase()
    if (!trimmedTicker) return
    if (needsThreshold && !threshold.trim()) {
      setError('This condition needs a threshold value.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await onAdd({ ticker: trimmedTicker, condition_type: conditionType, threshold_value: needsThreshold ? threshold.trim() : null })
      setTicker('')
      setThreshold('')
    } catch (err) {
      setError(err instanceof ApiError ? friendlyErrorMessage(err) : 'Could not create this alert.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
      <label className="flex flex-col gap-1 text-xs sm:w-32">
        <span className="metric-label">Ticker</span>
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="e.g. RELIANCE"
          autoComplete="off"
          spellCheck={false}
          className="input-field w-full px-3 py-2 font-mono-nums text-sm"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs sm:w-56">
        <span className="metric-label">Condition</span>
        <select
          value={conditionType}
          onChange={(e) => setConditionType(e.target.value as AlertConditionType)}
          className="input-field w-full px-3 py-2 text-sm"
        >
          {CONDITION_ORDER.map((key) => (
            <option key={key} value={key}>
              {CONDITION_LABEL[key]}
            </option>
          ))}
        </select>
      </label>
      {needsThreshold && (
        <label className="flex flex-col gap-1 text-xs sm:w-28">
          <span className="metric-label">Threshold</span>
          <input
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            placeholder="e.g. 2500"
            inputMode="decimal"
            className="input-field w-full px-3 py-2 font-mono-nums text-sm"
          />
        </label>
      )}
      <button type="submit" disabled={submitting || !ticker.trim()} className="btn-primary px-4 py-2 text-sm">
        {submitting ? 'Adding…' : 'Add alert'}
      </button>
      {error && (
        <p role="alert" className="text-xs text-[var(--color-status-negative)] sm:basis-full">
          {error}
        </p>
      )}
    </form>
  )
}
