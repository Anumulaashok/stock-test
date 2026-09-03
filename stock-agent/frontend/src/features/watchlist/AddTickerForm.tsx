import { useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { friendlyErrorMessage } from '../../components/ui/ErrorState'

/** Plain text input, not `SearchBar` -- that component's submit button is
 * hardcoded to "Analyze" (it drives the research flow), which would read
 * wrong for an "add to watchlist" action. */
export function AddTickerForm({ onAdd }: { onAdd: (ticker: string) => Promise<void> }) {
  const [value, setValue] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const ticker = value.trim().toUpperCase()
    if (!ticker) return
    setSubmitting(true)
    setError(null)
    try {
      await onAdd(ticker)
      setValue('')
    } catch (err) {
      setError(err instanceof ApiError ? friendlyErrorMessage(err) : 'Could not add to watchlist.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
      <label className="flex flex-col gap-1 text-xs sm:w-48">
        <span className="metric-label">Add a ticker</span>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value.toUpperCase())}
          placeholder="e.g. RELIANCE"
          autoComplete="off"
          spellCheck={false}
          className="input-field w-full px-3 py-2 font-mono-nums text-sm"
        />
      </label>
      <button type="submit" disabled={submitting || !value.trim()} className="btn-primary px-4 py-2 text-sm">
        {submitting ? 'Adding…' : 'Add to watchlist'}
      </button>
      {error && (
        <p role="alert" className="text-xs text-[var(--color-status-negative)] sm:basis-full">
          {error}
        </p>
      )}
    </form>
  )
}
