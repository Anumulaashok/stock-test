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
