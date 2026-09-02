import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { searchStocks, type StockSearchResult } from '../api/search'

interface SearchBarProps {
  onSubmit: (ticker: string) => void
  disabled: boolean
}

const DEBOUNCE_MS = 200

export function SearchBar({ onSubmit, disabled }: SearchBarProps) {
  const [value, setValue] = useState('')
  const [suggestions, setSuggestions] = useState<StockSearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(-1)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestIdRef = useRef(0)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const query = value.trim()
    if (!query) {
      setSuggestions([])
      setOpen(false)
      return
    }
    const thisRequestId = ++requestIdRef.current
    debounceRef.current = setTimeout(() => {
      searchStocks(query)
        .then((results) => {
          if (thisRequestId !== requestIdRef.current) return // a newer keystroke superseded this request
          setSuggestions(results)
          setOpen(results.length > 0)
          setHighlighted(-1)
        })
        .catch(() => {
          if (thisRequestId !== requestIdRef.current) return
          setSuggestions([])
          setOpen(false)
        })
    }, DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [value])

  function selectSuggestion(result: StockSearchResult) {
    setValue(result.symbol)
    setOpen(false)
    setSuggestions([])
    onSubmit(result.symbol)
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const ticker = value.trim()
    if (!ticker) return
    setOpen(false)
    onSubmit(ticker)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!open || suggestions.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlighted((i) => (i + 1) % suggestions.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlighted((i) => (i <= 0 ? suggestions.length - 1 : i - 1))
    } else if (event.key === 'Enter' && highlighted >= 0) {
      event.preventDefault()
      selectSuggestion(suggestions[highlighted])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="relative w-full max-w-lg">
      <form onSubmit={handleSubmit} className="flex w-full gap-2" aria-label="Stock ticker search">
        <label htmlFor="ticker-input" className="sr-only">
          Ticker symbol or company name
        </label>
        <div className="relative flex-1">
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            fill="none"
            className="pointer-events-none absolute left-3.5 top-1/2 h-4.5 w-4.5 -translate-y-1/2 text-[var(--color-text-faint)]"
          >
            <circle cx="9" cy="9" r="6.5" stroke="currentColor" strokeWidth="1.6" />
            <path d="M18 18L14 14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
          <input
            id="ticker-input"
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value.toUpperCase())}
            onKeyDown={handleKeyDown}
            onFocus={() => suggestions.length > 0 && setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            placeholder="RELIANCE or Reliance Industries"
            disabled={disabled}
            autoComplete="off"
            spellCheck={false}
            role="combobox"
            aria-expanded={open}
            aria-controls="ticker-suggestions"
            aria-autocomplete="list"
            className="input-field w-full py-2.5 pl-10 pr-3 font-mono-nums text-base tracking-wide text-[var(--color-text)] shadow-[var(--shadow-xs)] disabled:opacity-50 sm:text-lg"
          />
        </div>
        <button type="submit" disabled={disabled || !value.trim()} className="btn-primary px-5 py-2.5 text-sm sm:text-base">
          {disabled && (
            <span
              aria-hidden="true"
              className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white"
            />
          )}
          {disabled ? 'Analyzing…' : 'Analyze'}
        </button>
      </form>

      {open && suggestions.length > 0 && (
        <ul
          id="ticker-suggestions"
          role="listbox"
          className="animate-fade-in-up surface-card absolute z-10 mt-2 max-h-72 w-full overflow-y-auto p-1.5 shadow-[var(--shadow-lg)]"
        >
          {suggestions.map((result, index) => (
            <li
              key={result.symbol}
              role="option"
              aria-selected={index === highlighted}
              onMouseDown={(e) => e.preventDefault()} // keep the input focused so onBlur doesn't fire before the click registers
              onClick={() => selectSuggestion(result)}
              className={`flex cursor-pointer items-baseline gap-2 rounded-[var(--radius-sm)] border-l-2 px-2.5 py-2 text-sm transition-colors ${
                index === highlighted
                  ? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)]'
                  : 'border-transparent hover:bg-[var(--color-bg-subtle)]'
              }`}
            >
              <span className="font-mono-nums font-semibold text-[var(--color-text)]">{result.symbol}</span>
              <span className="truncate text-[var(--color-text-faint)]">{result.name}</span>
              <span className="ml-auto shrink-0 text-xs text-[var(--color-text-faint)]">{result.exchange}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
