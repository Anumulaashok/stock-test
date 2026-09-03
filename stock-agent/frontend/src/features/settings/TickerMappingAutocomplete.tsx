import { useEffect, useRef, useState } from 'react'
import { searchCompanies } from '../../api/marketHistory'
import type { CompanySearchResponse, CompanySearchResult } from '../../types/backend'

/** Extracted verbatim from `IntelligencePage`'s inline widget of the same
 * name (that copy is left in place for the lead to remove separately). */
export function TickerMappingAutocomplete({
  value,
  onChange,
  onPick,
}: {
  value: string
  onChange: (value: string) => void
  onPick: (result: CompanySearchResult) => void
}) {
  const [suggestions, setSuggestions] = useState<CompanySearchResult[]>([])
  const [source, setSource] = useState<CompanySearchResponse['source'] | null>(null)
  const [open, setOpen] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestIdRef = useRef(0)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const query = value.trim()
    if (query.length < 1) {
      setSuggestions([])
      setOpen(false)
      return
    }
    const thisRequestId = ++requestIdRef.current
    debounceRef.current = setTimeout(() => {
      searchCompanies(query)
        .then((response) => {
          if (thisRequestId !== requestIdRef.current) return
          setSuggestions(response.results)
          setSource(response.source)
          setOpen(response.results.length > 0)
        })
        .catch(() => {
          if (thisRequestId !== requestIdRef.current) return
          setSuggestions([])
          setOpen(false)
        })
    }, 250)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [value])

  return (
    <div className="relative">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase())}
        onFocus={() => suggestions.length > 0 && setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        placeholder="Ticker or company name, e.g. HDFCBANK"
        className="input-field w-full px-3 py-2 text-sm"
      />
      {open && (
        <ul className="absolute z-10 mt-1 w-max min-w-full max-w-[360px] overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] shadow-[var(--shadow-md)]">
          {suggestions.map((s) => (
            <li key={s.ticker}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onPick(s)
                  setOpen(false)
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-[var(--color-accent-soft)]"
              >
                <span className="min-w-0 flex-1 truncate">
                  <span className="font-medium">{s.ticker}</span>
                  {s.company_name && <span className="ml-2 truncate text-[var(--color-text-faint)]">{s.company_name}</span>}
                </span>
                <span className="shrink-0 font-mono-nums text-xs text-[var(--color-text-faint)]">
                  {s.screener_company_id !== null ? `#${s.screener_company_id}` : '—'}
                </span>
              </button>
            </li>
          ))}
          <li className="border-t border-[var(--color-border)] px-3 py-1.5 text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">
            Source: {source === 'screener' ? 'Screener.in (live)' : 'Local NSE directory'}
          </li>
        </ul>
      )}
    </div>
  )
}
