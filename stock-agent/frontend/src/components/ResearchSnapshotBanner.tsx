import { SectionHeader } from './SectionHeader'
import { formatDateTime } from '../lib/format'
import type { ResearchRunResult } from '../types/backend'

const RUN_TYPE_LABEL: Record<string, string> = {
  NORMAL: 'Normal',
  FORCE_REFRESH: 'Force Refresh',
}

/**
 * Makes it explicit whether the page is showing an already-saved
 * research snapshot or one just computed, and when it was produced --
 * never lets the page imply every load is real-time data (see
 * `app/snapshot/` on the backend: a normal search reuses today's
 * completed snapshot rather than recomputing).
 */
export function ResearchSnapshotBanner({
  run,
  refreshing,
  onRefresh,
  onForceRefresh,
}: {
  run: ResearchRunResult
  refreshing: boolean
  onRefresh: () => void
  onForceRefresh: () => void
}) {
  const timestamp = formatDateTime(run.completed_at ?? run.started_at)

  return (
    <SectionHeader
      id="research-snapshot-heading"
      title="Research Snapshot"
      subtitle={
        timestamp
          ? `${timestamp}${run.is_new_run ? '' : ' · reused from a saved snapshot'}${
              run.run_type === 'FORCE_REFRESH' ? ` · ${RUN_TYPE_LABEL[run.run_type]}` : ''
            }`
          : undefined
      }
      action={
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="inline-flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            Refresh
          </button>
          <button
            type="button"
            onClick={onForceRefresh}
            disabled={refreshing}
            title="Ignore the saved snapshot and run a fresh analysis"
            className="inline-flex items-center rounded-[var(--radius-sm)] border border-[var(--color-accent)]/40 bg-[var(--color-accent-soft)] px-3 py-1.5 text-sm font-medium text-[var(--color-accent-strong)] transition-colors disabled:cursor-not-allowed disabled:opacity-60"
          >
            {refreshing ? 'Refreshing…' : 'Force Refresh'}
          </button>
        </div>
      }
    />
  )
}
