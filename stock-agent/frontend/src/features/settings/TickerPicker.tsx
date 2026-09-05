import { useState, type FormEvent } from 'react'

/**
 * Shared ticker-entry control for the two Settings pages that have no
 * cross-ticker endpoint to fall back to (Data Quality, Model
 * Performance) -- each renders per-ticker data only once a ticker is
 * chosen here.
 */
export function TickerPicker({
  initialValue = '',
  onSubmit,
  placeholder = 'e.g. RELIANCE',
  label = 'Ticker symbol',
}: {
  initialValue?: string
  onSubmit: (ticker: string) => void
  placeholder?: string
  label?: string
}) {
  const [input, setInput] = useState(initialValue)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const ticker = input.trim().toUpperCase()
    if (!ticker) return
    onSubmit(ticker)
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2" aria-label="Ticker picker">
      <label htmlFor="settings-ticker-input" className="sr-only">
        {label}
      </label>
      <input
        id="settings-ticker-input"
        value={input}
        onChange={(e) => setInput(e.target.value.toUpperCase())}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
        className="input-field flex-1 px-3 py-2 font-mono-nums text-sm"
      />
      <button type="submit" disabled={!input.trim()} className="btn-primary px-4 py-2 text-sm">
        View
      </button>
    </form>
  )
}
