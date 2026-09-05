import type { DataSourceStatus } from '../types/backend'

export type Tone = 'ok' | 'warn' | 'bad' | 'idle'

export const STATUS_TONE: Record<string, Tone> = {
  SUCCESS: 'ok',
  UNKNOWN: 'idle',
  NOT_CONFIGURED: 'idle',
  RATE_LIMITED: 'warn',
  UNREACHABLE: 'warn',
  AUTH_EXPIRED: 'bad',
  INVALID: 'bad',
}

export const STATUS_LABEL: Record<string, string> = {
  SUCCESS: 'Connected',
  UNKNOWN: 'Not checked',
  NOT_CONFIGURED: 'Not configured',
  RATE_LIMITED: 'Rate limited',
  UNREACHABLE: 'Unreachable',
  AUTH_EXPIRED: 'Expired',
  INVALID: 'Invalid response',
}

export const CATEGORY_LABEL: Record<string, string> = {
  financials: 'Financials',
  market_quote: 'Market data',
  historical_price: 'Historical',
  company_search: 'Search',
}

export function toneFor(source: DataSourceStatus): Tone {
  if (!source.configured) return 'idle'
  return STATUS_TONE[source.status] ?? 'idle'
}

export function roleLabel(source: DataSourceStatus): string | null {
  const primary = source.primary_for.map((c) => CATEGORY_LABEL[c] ?? c)
  const fallback = source.fallback_for.map((c) => CATEGORY_LABEL[c] ?? c)
  const parts: string[] = []
  if (primary.length) parts.push(`${primary.join(', ')} · Primary`)
  if (fallback.length) parts.push(`${fallback.join(', ')} · Fallback`)
  return parts.length ? parts.join('  ') : null
}

/**
 * Per-source health bucket for the compact sidebar badge -- deliberately
 * coarser than `toneFor`. A documented, permanent `limitation` (e.g.
 * FMP's HTTP 402 on every NSE/BSE symbol) reads the same as a live
 * fallback-covered failure: both are "serving normally, with a caveat,"
 * never an alarm. Only AUTH_EXPIRED/INVALID -- a real, uncovered
 * failure -- earns the action-required treatment.
 */
export type HealthBucket = 'healthy' | 'degradedServing' | 'actionRequired' | 'idle'

export function bucketFor(source: DataSourceStatus): HealthBucket {
  if (!source.configured) return 'idle'
  if (source.status === 'AUTH_EXPIRED' || source.status === 'INVALID') return 'actionRequired'
  if (source.status === 'RATE_LIMITED' || source.status === 'UNREACHABLE') return 'degradedServing'
  if (source.limitation) return 'degradedServing'
  if (source.status === 'SUCCESS') return 'healthy'
  return 'idle'
}

export type OverallHealth =
  | { kind: 'healthy' }
  | { kind: 'degradedServing'; sources: DataSourceStatus[] }
  | { kind: 'actionRequired'; sources: DataSourceStatus[] }
  | { kind: 'noneConfigured' }

/**
 * Worst bucket among configured sources wins -- a single AUTH_EXPIRED
 * source makes the whole badge read as action-required even while every
 * other source is healthy. Unconfigured sources never count toward any
 * bucket -- absence isn't degradation.
 */
export function classifyOverallHealth(sources: DataSourceStatus[]): OverallHealth {
  const configured = sources.filter((s) => s.configured)
  if (configured.length === 0) return { kind: 'noneConfigured' }

  const actionRequired = configured.filter((s) => bucketFor(s) === 'actionRequired')
  if (actionRequired.length > 0) return { kind: 'actionRequired', sources: actionRequired }

  const degraded = configured.filter((s) => bucketFor(s) === 'degradedServing')
  if (degraded.length > 0) return { kind: 'degradedServing', sources: degraded }

  return { kind: 'healthy' }
}
