/**
 * Presentation-only helpers. These parse the backend's decimal *strings*
 * for display precision — they never derive a new financial value. Any
 * value with a backend-provided `formatted_*` field should use that
 * directly instead of these.
 */

export function toDisplayNumber(value: string | null | undefined, decimals = 1): string | null {
  if (value === null || value === undefined) return null
  const parsed = Number(value)
  if (Number.isNaN(parsed)) return null
  return parsed.toFixed(decimals)
}

export function formatDate(value: string | null | undefined): string | null {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(value: string | null | undefined): string | null {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return (
    parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) +
    ' · ' +
    parsed.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  )
}

export function humanizeKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Only http(s) links are ever rendered as clickable — anything else
 * (javascript:, data:, file:, malformed) renders as inert text instead. */
export function isSafeHttpUrl(value: string | null | undefined): value is string {
  if (!value) return false
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

/** Fallback formatters for when the backend hasn't already supplied a
 * `formatted_*` string for this value — prefer the backend's own field
 * whenever one exists; these exist only to stop each component from
 * writing its own local copy (previously duplicated in DashboardPage,
 * ForecastSection, and IntelligencePage). */

export function formatCurrency(value: string | number | null | undefined, currency = 'INR'): string | null {
  if (value === null || value === undefined) return null
  const parsed = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(parsed)) return null
  const symbol = currency === 'INR' ? '₹' : ''
  return `${symbol}${parsed.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

/** Indian numbering (Lakh/Crore) compact form for large rupee figures. */
export function formatCompactINR(value: string | number | null | undefined): string | null {
  if (value === null || value === undefined) return null
  const parsed = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(parsed)) return null
  const abs = Math.abs(parsed)
  const sign = parsed < 0 ? '-' : ''
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(2)} Cr`
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(2)} L`
  return formatCurrency(parsed)
}

export function formatPercent(value: string | number | null | undefined, decimals = 1): string | null {
  if (value === null || value === undefined) return null
  const parsed = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(parsed)) return null
  return `${parsed.toFixed(decimals)}%`
}

/** Same as `formatPercent` but always shows a leading sign — for
 * changes/deltas, never for absolute levels. */
export function formatSignedPercent(value: string | number | null | undefined, decimals = 1): string | null {
  if (value === null || value === undefined) return null
  const parsed = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(parsed)) return null
  const sign = parsed >= 0 ? '+' : ''
  return `${sign}${parsed.toFixed(decimals)}%`
}

export function formatMultiple(value: string | number | null | undefined, decimals = 1): string | null {
  if (value === null || value === undefined) return null
  const parsed = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(parsed)) return null
  return `${parsed.toFixed(decimals)}x`
}
