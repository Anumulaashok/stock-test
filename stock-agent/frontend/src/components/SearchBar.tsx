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
    <div className="relative w-full max-w-md">
      <form onSubmit={handleSubmit} className="flex w-full gap-2" aria-label="Stock ticker search">
        <label htmlFor="ticker-input" className="sr-only">
          Ticker symbol or company name
        </label>
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

      {open && suggestions.length > 0 && (
        <ul
          id="ticker-suggestions"
          role="listbox"
          className="absolute z-10 mt-1 max-h-72 w-full overflow-y-auto rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] shadow-lg"
        >
          {suggestions.map((result, index) => (
            <li
              key={result.symbol}
              role="option"
              aria-selected={index === highlighted}
              onMouseDown={(e) => e.preventDefault()} // keep the input focused so onBlur doesn't fire before the click registers
              onClick={() => selectSuggestion(result)}
              className={`cursor-pointer px-3 py-2 text-sm ${
                index === highlighted ? 'bg-[var(--color-accent)] text-white' : 'text-[var(--color-text)]'
              }`}
            >
              <span className="font-mono-nums font-semibold">{result.symbol}</span>
              <span className={`ml-2 ${index === highlighted ? 'text-white/80' : 'text-[var(--color-text-faint)]'}`}>
                {result.name}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
