import { useState } from 'react'
import { ApiError } from '../../api/client'
import { registerScreenerCompanyMappings } from '../../api/marketHistory'

/** Extracted from `IntelligencePage`'s `MappingListImportWidget` -- bulk
 * ticker->screener-id mapping import (paste Screener's own
 * company-search JSON, reused going forward for autocomplete +
 * auto-lookup). */
export function MappingImportCard() {
  const [raw, setRaw] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)

  async function handleImport() {
    let parsed: unknown
    try {
      parsed = JSON.parse(raw)
    } catch {
      setStatus('error')
      setMessage('That is not valid JSON — paste the array exactly as Screener returned it.')
      return
    }
    if (!Array.isArray(parsed)) {
      setStatus('error')
      setMessage('Expected a JSON array of {id, name, url} objects.')
      return
    }
    setStatus('loading')
    setMessage(null)
    try {
      const result = await registerScreenerCompanyMappings(parsed)
      setStatus('success')
      setMessage(
        `Registered ${result.registered} ticker${result.registered === 1 ? '' : 's'}` +
          (result.skipped > 0 ? ` (${result.skipped} skipped — no id or unparseable url).` : '.'),
      )
      setRaw('')
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof ApiError ? err.message : 'Import failed.')
    }
  }

  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <div>
        <h2 className="card-heading">Bulk-Register Screener IDs</h2>
        <p className="support-text">
          Paste a Screener company-search JSON result (a list of <code className="font-mono-nums">{'{id, name, url}'}</code>{' '}
          objects) to register every ticker → Screener-id mapping at once — reused automatically by the ticker
          autocomplete above and by future imports, so you never look the id up twice.
        </p>
      </div>
      <textarea
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        placeholder='[{"id": 681, "name": "Coal India Ltd", "url": "/company/COALINDIA/consolidated/"}, ...]'
        rows={4}
        className="input-field w-full px-3 py-2 font-mono-nums text-xs"
      />
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleImport}
          disabled={status === 'loading' || !raw.trim()}
          className="btn-primary px-4 py-2 text-sm"
        >
          {status === 'loading' ? 'Registering…' : 'Register list'}
        </button>
        {message && (
          <p className={`text-xs ${status === 'error' ? 'text-[var(--color-status-critical)]' : 'text-[var(--color-status-positive)]'}`}>
            {message}
          </p>
        )}
      </div>
    </div>
  )
}
