import { useCallback, useEffect, useState } from 'react'

import { fetchDataSourceStatus } from '../api/dataSources'
import type { DataSourceStatus } from '../types/backend'

/**
 * Makes the source strategy visible: which source owns each category,
 * whether it is working, and when a fallback is carrying the load.
 *
 * Every value comes from GET /api/v1/market/data-sources/status -- there is
 * no placeholder or optimistic state here. A source whose status is unknown
 * says so rather than showing green.
 */

type Tone = 'ok' | 'warn' | 'bad' | 'idle'

const STATUS_TONE: Record<string, Tone> = {
  SUCCESS: 'ok',
  UNKNOWN: 'idle',
  NOT_CONFIGURED: 'idle',
  RATE_LIMITED: 'warn',
  UNREACHABLE: 'warn',
  AUTH_EXPIRED: 'bad',
  INVALID: 'bad',
  ERROR: 'bad',
}

const STATUS_LABEL: Record<string, string> = {
  SUCCESS: 'Connected',
  UNKNOWN: 'Not checked',
  NOT_CONFIGURED: 'Not configured',
  RATE_LIMITED: 'Rate limited',
  UNREACHABLE: 'Unreachable',
  AUTH_EXPIRED: 'Expired',
  INVALID: 'Invalid response',
  ERROR: 'Error',
}

const CATEGORY_LABEL: Record<string, string> = {
  financials: 'Financials',
  market_quote: 'Market data',
  historical_price: 'Historical',
  company_search: 'Search',
}

const TONE_STYLE: Record<Tone, { dot: string; text: string }> = {
  ok: { dot: 'var(--color-status-positive)', text: 'var(--color-status-positive)' },
  warn: { dot: 'var(--color-status-medium)', text: 'var(--color-status-medium)' },
  bad: { dot: 'var(--color-status-critical)', text: 'var(--color-status-critical)' },
  idle: { dot: 'var(--color-text-faint)', text: 'var(--color-text-faint)' },
}

function toneFor(source: DataSourceStatus): Tone {
  if (!source.configured) return 'idle'
  return STATUS_TONE[source.status] ?? 'idle'
}

function relativeTime(iso: string | null): string | null {
  if (!iso) return null
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return null
  const seconds = Math.round((Date.now() - then) / 1000)
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)} hr ago`
  return `${Math.floor(seconds / 86_400)} d ago`
}

function roleLabel(source: DataSourceStatus): string | null {
  const primary = source.primary_for.map((c) => CATEGORY_LABEL[c] ?? c)
  const fallback = source.fallback_for.map((c) => CATEGORY_LABEL[c] ?? c)
  const parts: string[] = []
  if (primary.length) parts.push(`${primary.join(', ')} · Primary`)
  if (fallback.length) parts.push(`${fallback.join(', ')} · Fallback`)
  return parts.length ? parts.join('  ') : null
}

function SourceRow({ source }: { source: DataSourceStatus }) {
  const tone = toneFor(source)
  const style = TONE_STYLE[tone]
  const status = source.configured ? source.status : 'NOT_CONFIGURED'
  const lastSuccess = relativeTime(source.last_success_at)
  const role = roleLabel(source)

  return (
    <li className="flex flex-col gap-1 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          {source.label}
        </span>
        <span className="inline-flex items-center gap-1.5 text-[0.6875rem] font-semibold">
          <span
            aria-hidden="true"
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: style.dot }}
          />
          <span style={{ color: style.text }}>{STATUS_LABEL[status] ?? status}</span>
        </span>
      </div>

      {role ? (
        <span className="text-[0.6875rem]" style={{ color: 'var(--color-text-muted)' }}>
          {role}
        </span>
      ) : null}

      {lastSuccess ? (
        <span className="text-[0.6875rem]" style={{ color: 'var(--color-text-faint)' }}>
          Last success {lastSuccess}
        </span>
      ) : null}

      {source.limitation ? (
        <span className="text-[0.6875rem]" style={{ color: 'var(--color-text-faint)' }}>
          {source.limitation}
        </span>
      ) : null}
    </li>
  )
}

export default function DataSourcesPanel() {
  const [sources, setSources] = useState<DataSourceStatus[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    fetchDataSourceStatus()
      .then((response) => {
        setSources(response.sources)
        setError(null)
      })
      .catch(() => {
        setSources(null)
        setError('Source status is unavailable.')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const degraded = (sources ?? []).filter(
    (s) => s.configured && toneFor(s) !== 'ok' && toneFor(s) !== 'idle',
  )

  return (
    <section className="surface-card animate-fade-in-up overflow-hidden" aria-label="Data sources">
      <div
        className="flex items-center justify-between gap-3 px-4 py-3"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <p className="section-heading" style={{ margin: 0 }}>
          Data sources
        </p>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="text-[0.6875rem] font-semibold disabled:opacity-50"
          style={{ color: 'var(--color-accent-strong)' }}
        >
          {loading ? 'Checking…' : 'Refresh'}
        </button>
      </div>

      {degraded.length > 0 ? (
        <p
          className="px-4 py-2 text-[0.6875rem]"
          style={{
            color: 'var(--color-status-medium)',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          {degraded.map((s) => s.label).join(', ')} unavailable — fallback active.
        </p>
      ) : null}

      {error ? (
        <p className="px-4 py-3 text-[0.75rem]" style={{ color: 'var(--color-text-muted)' }}>
          {error}
        </p>
      ) : loading && sources === null ? (
        <p className="px-4 py-3 text-[0.75rem]" style={{ color: 'var(--color-text-faint)' }}>
          Checking sources…
        </p>
      ) : sources && sources.length > 0 ? (
        <ul className="divide-y" style={{ borderColor: 'var(--color-border)' }}>
          {sources.map((source) => (
            <SourceRow key={source.name} source={source} />
          ))}
        </ul>
      ) : (
        <p className="px-4 py-3 text-[0.75rem]" style={{ color: 'var(--color-text-muted)' }}>
          No data sources are configured.
        </p>
      )}
    </section>
  )
}
