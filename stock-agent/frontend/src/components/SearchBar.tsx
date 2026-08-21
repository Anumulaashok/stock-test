import { useState, type FormEvent } from 'react'

interface SearchBarProps {
  onSubmit: (ticker: string) => void
  disabled: boolean
}

export function SearchBar({ onSubmit, disabled }: SearchBarProps) {
  const [value, setValue] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const ticker = value.trim()
    if (ticker) onSubmit(ticker)
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-md gap-2" aria-label="Stock ticker search">
      <label htmlFor="ticker-input" className="sr-only">
        Ticker symbol
      </label>
      <input
        id="ticker-input"
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value.toUpperCase())}
        placeholder="AAPL"
        disabled={disabled}
        autoComplete="off"
        spellCheck={false}
        className="flex-1 rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-3 py-2 font-mono-nums text-lg tracking-wide text-[var(--color-text)] placeholder:text-[var(--color-text-faint)] focus:border-[var(--color-accent)] disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="rounded bg-[var(--color-accent)] px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {disabled ? 'Analyzing…' : 'Analyze'}
      </button>
    </form>
  )
}
