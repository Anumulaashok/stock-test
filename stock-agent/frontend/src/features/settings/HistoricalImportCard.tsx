import { useState } from 'react'
import { ApiError } from '../../api/client'
import { importHistoricalPrices } from '../../api/marketHistory'
import { TickerMappingAutocomplete } from './TickerMappingAutocomplete'

/** Extracted from `IntelligencePage`'s `HistoricalImportWidget` -- a
 * one-time, manually-triggered backfill from Screener.in. */
export function HistoricalImportCard() {
  const [ticker, setTicker] = useState('')
  const [companyId, setCompanyId] = useState('')
  const [days, setDays] = useState('365')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)

  async function handleImport() {
    if (!ticker.trim()) return
    setStatus('loading')
    setMessage(null)
    try {
      const result = await importHistoricalPrices(ticker, {
        screener_company_id: companyId.trim() ? Number(companyId) : null,
        days: Number(days) || 365,
        consolidated: true,
      })
      setStatus('success')
      setMessage(
        `Imported ${result.rows_imported} day${result.rows_imported === 1 ? '' : 's'}` +
          (result.earliest_date && result.latest_date ? ` (${result.earliest_date} → ${result.latest_date}).` : '.'),
      )
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof ApiError ? err.message : 'Import failed.')
    }
  }

  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <div>
        <h2 className="card-heading">Import Historical Data</h2>
        <p className="support-text">
          One-time backfill from Screener.in. Start typing a ticker — if it's already mapped (via a prior import or
          the bulk list-import below), pick it and the Screener id fills in automatically; otherwise enter the id
          manually once and it's remembered from then on.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_100px_auto]">
        <TickerMappingAutocomplete
          value={ticker}
          onChange={setTicker}
          onPick={(result) => {
            setTicker(result.ticker)
            setCompanyId(result.screener_company_id !== null ? String(result.screener_company_id) : '')
          }}
        />
        <input
          value={companyId}
          onChange={(e) => setCompanyId(e.target.value)}
          type="number"
          min="1"
          placeholder="Screener company id (optional if mapped)"
          className="input-field px-3 py-2 text-sm"
        />
        <input
          value={days}
          onChange={(e) => setDays(e.target.value)}
          type="number"
          min="1"
          placeholder="Days"
          className="input-field px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={handleImport}
          disabled={status === 'loading' || !ticker.trim()}
          className="btn-primary px-4 py-2 text-sm"
        >
          {status === 'loading' ? 'Importing…' : 'Import'}
        </button>
      </div>
      {message && (
        <p className={`text-xs ${status === 'error' ? 'text-[var(--color-status-critical)]' : 'text-[var(--color-status-positive)]'}`}>
          {message}
        </p>
      )}
    </div>
  )
}
