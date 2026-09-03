import { useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { clearScreenerCookie, fetchScreenerCookieStatus, setScreenerCookie } from '../../api/marketHistory'
import type { ScreenerCookieStatus } from '../../types/backend'

/**
 * Distinguishes "a cookie is stored" from "the stored cookie works" --
 * previously any stored cookie showed as Active, including an expired
 * one. Never renders the cookie value itself, only a status word.
 */
function ScreenerCookieBadge({ status }: { status: ScreenerCookieStatus }) {
  if (!status.configured) {
    return (
      <span className="badge shrink-0 bg-[var(--color-status-medium)]/15 text-[var(--color-status-medium)]">
        Not configured
      </span>
    )
  }

  const bad = status.status === 'AUTH_EXPIRED' || status.status === 'INVALID'
  const warn = status.status === 'UNREACHABLE' || status.status === 'RATE_LIMITED'
  const label =
    status.status === 'SUCCESS'
      ? `Valid (${status.source})`
      : status.status === 'AUTH_EXPIRED'
        ? 'Expired — re-authenticate'
        : status.status === 'INVALID'
          ? 'Invalid response'
          : status.status === 'UNREACHABLE'
            ? 'Screener unreachable'
            : status.status === 'RATE_LIMITED'
              ? 'Rate limited'
              : `Stored (${status.source}) — not checked`

  const tone = bad
    ? 'bg-[var(--color-status-critical)]/15 text-[var(--color-status-critical)]'
    : warn
      ? 'bg-[var(--color-status-medium)]/15 text-[var(--color-status-medium)]'
      : status.status === 'SUCCESS'
        ? 'bg-[var(--color-status-positive)]/15 text-[var(--color-status-positive)]'
        : 'bg-[var(--color-status-info)]/15 text-[var(--color-status-info)]'

  return (
    <span className={`badge shrink-0 ${tone}`} title={status.detail ?? undefined}>
      {label}
    </span>
  )
}

/** Extracted from `IntelligencePage`'s `ScreenerCookieSettingsWidget` --
 * runtime-editable (no server restart), takes effect immediately for
 * live company search and gets used by future imports. */
export function ScreenerCookieCard() {
  const [status, setStatus] = useState<ScreenerCookieStatus | null>(null)
  const [cookieInput, setCookieInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  function load() {
    fetchScreenerCookieStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
  }

  useEffect(() => {
    load()
  }, [])

  async function handleSave() {
    if (!cookieInput.trim()) return
    setSaving(true)
    setMessage(null)
    try {
      const result = await setScreenerCookie(cookieInput.trim())
      setStatus(result)
      setCookieInput('')
      setMessage('Cookie saved — live Screener search is active immediately, no restart needed.')
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : 'Could not save the cookie.')
    } finally {
      setSaving(false)
    }
  }

  async function handleClear() {
    setSaving(true)
    setMessage(null)
    try {
      const result = await clearScreenerCookie()
      setStatus(result)
      setMessage(
        result.configured
          ? 'Runtime cookie cleared — falling back to the server-configured one.'
          : 'Cookie cleared — company search now uses the local NSE directory.',
      )
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : 'Could not clear the cookie.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="card-heading">Screener.in Session</h2>
          <p className="support-text">
            Paste your Screener <code className="font-mono-nums">sessionid</code> cookie value to enable live company
            search (used to resolve tickers to Screener ids). Without it, company search falls back to the local NSE
            directory — Screener imports and Nifty 50 / Sensex both keep working either way.
          </p>
        </div>
        {status && <ScreenerCookieBadge status={status} />}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={cookieInput}
          onChange={(e) => setCookieInput(e.target.value)}
          type="password"
          placeholder="Paste sessionid cookie value…"
          className="input-field min-w-0 flex-1 px-3 py-2 font-mono-nums text-xs"
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !cookieInput.trim()}
            className="btn-primary px-4 py-2 text-sm"
          >
            Save
          </button>
          {status?.source === 'runtime' && (
            <button type="button" onClick={handleClear} disabled={saving} className="btn-secondary px-4 py-2 text-sm">
              Clear
            </button>
          )}
        </div>
      </div>
      {message && <p className="text-xs text-[var(--color-text-faint)]">{message}</p>}
    </div>
  )
}
