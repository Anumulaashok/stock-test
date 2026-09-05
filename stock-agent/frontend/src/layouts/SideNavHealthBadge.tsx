import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useDataSourceStatus, type DataSourceStatusPhase } from '../dataSources/DataSourceStatusContext'
import { classifyOverallHealth, roleLabel, STATUS_LABEL } from '../lib/dataSourceStatus'
import { paths } from '../routes/paths'
import type { DataSourceStatus } from '../types/backend'

/** Shape + color both carry meaning (never color alone): circle=healthy,
 * diamond=serving with a caveat, triangle=needs attention, square=unknown. */
function Shape({ kind, color }: { kind: 'circle' | 'diamond' | 'triangle' | 'square'; color: string }) {
  const common = { width: 8, height: 8, background: color, flexShrink: 0 } as const
  if (kind === 'circle') return <span aria-hidden="true" style={{ ...common, borderRadius: '50%' }} />
  if (kind === 'diamond') return <span aria-hidden="true" style={{ ...common, transform: 'rotate(45deg)' }} />
  if (kind === 'triangle') {
    return (
      <span
        aria-hidden="true"
        style={{ width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderBottom: `8px solid ${color}`, flexShrink: 0 }}
      />
    )
  }
  return <span aria-hidden="true" style={{ ...common, borderRadius: 2 }} />
}

function SourceLine({ source }: { source: DataSourceStatus }) {
  const role = roleLabel(source)
  return (
    <li className="flex flex-col gap-0.5 py-1.5">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-medium text-[var(--color-text)]">{source.label}</span>
        <span className="text-[var(--color-text-muted)]">{STATUS_LABEL[source.status] ?? source.status}</span>
      </div>
      {role && <span className="text-[0.65rem] text-[var(--color-text-faint)]">{role}</span>}
      {source.limitation && <span className="text-[0.65rem] text-[var(--color-text-faint)]">{source.limitation}</span>}
      {source.status === 'AUTH_EXPIRED' && (
        <Link to={paths.settings('system')} className="text-[0.65rem] font-semibold text-[var(--color-accent-strong)] underline">
          Fix session cookie
        </Link>
      )}
    </li>
  )
}

/**
 * Exported for the dev-only fixture route (`src/dev/HealthBadgeFixturePage.tsx`)
 * -- renders every phase/health combination directly against fabricated
 * `phase`/`sources`, with zero network calls, so all of them (including
 * the failed-fetch "unknown" state) can be eyeballed side by side. Not
 * used by any other production call site; `SideNavHealthBadge` below is
 * the one real caller.
 */
export function HealthBadgeView({
  phase,
  sources,
  reload,
}: {
  phase: DataSourceStatusPhase
  sources: DataSourceStatus[] | null
  reload: () => void
}) {
  const [expanded, setExpanded] = useState(false)

  if (phase === 'error') {
    return (
      <div className="flex flex-col gap-1 rounded-[var(--radius-md)] border border-[var(--color-border)] px-3 py-2">
        <div className="flex items-center gap-2 text-xs">
          <Shape kind="square" color="var(--color-text-faint)" />
          <span className="text-[var(--color-text-muted)]">Source status unknown</span>
        </div>
        <button type="button" onClick={reload} className="self-start text-[0.65rem] font-semibold text-[var(--color-accent-strong)] underline">
          Retry
        </button>
      </div>
    )
  }

  if (phase === 'loading' || sources === null) {
    return (
      <div className="flex items-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-border)] px-3 py-2 text-xs">
        <Shape kind="square" color="var(--color-text-faint)" />
        <span className="text-[var(--color-text-faint)]">Checking sources…</span>
      </div>
    )
  }

  const health = classifyOverallHealth(sources)

  let shapeKind: 'circle' | 'diamond' | 'triangle' | 'square' = 'square'
  let color = 'var(--color-text-faint)'
  let label = 'No sources configured'

  if (health.kind === 'healthy') {
    shapeKind = 'circle'
    color = 'var(--color-status-positive)'
    label = 'All sources healthy'
  } else if (health.kind === 'degradedServing') {
    shapeKind = 'diamond'
    // Deliberately the accent blue, not `--color-status-info`'s muted
    // gray -- that gray reads too close to the idle/unknown state's
    // color at 8px, undermining the point of this bucket (informative,
    // not ignorable, but not an alarm either).
    color = 'var(--color-accent)'
    label = `Serving normally — ${health.sources.length} noted`
  } else if (health.kind === 'actionRequired') {
    shapeKind = 'triangle'
    color = 'var(--color-status-critical)'
    label =
      health.sources.length === 1
        ? `${health.sources[0].label} needs attention`
        : `${health.sources.length} sources need attention`
  }

  return (
    <div className="flex flex-col gap-2 rounded-[var(--radius-md)] border border-[var(--color-border)] px-3 py-2">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex items-center gap-2 text-left text-xs"
      >
        <Shape kind={shapeKind} color={color} />
        <span style={{ color }} className="flex-1 truncate">
          {label}
        </span>
      </button>

      {expanded && (
        <ul className="flex flex-col divide-y divide-[var(--color-border)] border-t border-[var(--color-border)] pt-1">
          {sources.map((source) => (
            <SourceLine key={source.name} source={source} />
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * Compact, always-visible data-source health indicator in the sidebar
 * footer -- global state, not ticker-scoped (see `StockHeader`, which
 * is). Reads `DataSourceStatusProvider` (mounted once in `AppShell`)
 * rather than fetching its own copy.
 */
export function SideNavHealthBadge() {
  const { phase, sources, reload } = useDataSourceStatus()
  return <HealthBadgeView phase={phase} sources={sources} reload={reload} />
}
