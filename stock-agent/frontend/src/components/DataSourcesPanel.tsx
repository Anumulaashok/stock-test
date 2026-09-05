import { useDataSourceStatus } from '../dataSources/DataSourceStatusContext'
import { roleLabel, STATUS_LABEL, toneFor, type Tone } from '../lib/dataSourceStatus'
import type { DataSourceStatus } from '../types/backend'

/**
 * Makes the source strategy visible: which source owns each category,
 * whether it is working, and when a fallback is carrying the load.
 *
 * Every value comes from GET /api/v1/market/data-sources/status, fetched
 * once for the whole app by `DataSourceStatusProvider` (mounted in
 * `AppShell`, shared with the sidebar health badge) -- this panel never
 * fires its own request. There is no placeholder or optimistic state: a
 * source whose status is unknown says so rather than showing green.
 */

const TONE_STYLE: Record<Tone, { dot: string; text: string }> = {
  ok: { dot: 'var(--color-status-positive)', text: 'var(--color-status-positive)' },
  warn: { dot: 'var(--color-status-medium)', text: 'var(--color-status-medium)' },
  bad: { dot: 'var(--color-status-critical)', text: 'var(--color-status-critical)' },
  idle: { dot: 'var(--color-text-faint)', text: 'var(--color-text-faint)' },
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
  const { phase, sources, reload } = useDataSourceStatus()
  const loading = phase === 'loading'

  const degraded = (sources ?? []).filter((s) => s.configured && toneFor(s) !== 'ok' && toneFor(s) !== 'idle')

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
          onClick={reload}
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

      {phase === 'error' ? (
        <p className="px-4 py-3 text-[0.75rem]" style={{ color: 'var(--color-text-muted)' }}>
          Source status is unavailable.
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
