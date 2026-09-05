import { useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { addHolding } from '../../api/portfolio'

function parsePositive(value: string): boolean {
  const trimmed = value.trim()
  if (!trimmed) return false
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) && parsed > 0
}

/** Rendered outside `AsyncSection` -- it doesn't read `summary`, so it
 * shouldn't unmount/remount every time `reload()` drops the table back
 * to a loading skeleton. */
export function AddHoldingForm({ onAdded }: { onAdded: () => void }) {
  const [ticker, setTicker] = useState('')
  const [quantity, setQuantity] = useState('')
  const [averageCost, setAverageCost] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!ticker.trim()) {
      setError('Enter a ticker.')
      return
    }
    if (!parsePositive(quantity) || !parsePositive(averageCost)) {
      setError('Quantity and average cost must be positive numbers.')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      await addHolding(ticker, quantity.trim(), averageCost.trim())
      setTicker('')
      setQuantity('')
      setAverageCost('')
      onAdded()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add holding.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="surface-card flex flex-wrap items-end gap-3 p-4">
      <label className="flex flex-col gap-1 text-xs">
        Ticker
        <input
          id="add-holding-ticker-input"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          required
          className="input-field w-24 px-2 py-1.5 text-sm"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs">
        Quantity
        <input
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          type="number"
          step="any"
          required
          className="input-field w-28 px-2 py-1.5 text-sm"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs">
        Avg Cost
        <input
          value={averageCost}
          onChange={(e) => setAverageCost(e.target.value)}
          type="number"
          step="any"
          required
          className="input-field w-28 px-2 py-1.5 text-sm"
        />
      </label>
      <button type="submit" disabled={submitting} className="btn-primary px-4 py-1.5 text-sm">
        {submitting ? 'Adding…' : 'Add holding'}
      </button>
      {error && <p className="w-full text-xs text-[var(--color-status-negative)]">{error}</p>}
    </form>
  )
}
