import { Link } from 'react-router-dom'
import { fetchRecentResearch } from '../api/research'
import { useAsync } from '../hooks/useAsync'
import { AsyncSection } from '../components/ui/AsyncSection'
import { paths } from '../routes/paths'
import { toDisplayNumber, formatDateTime } from '../lib/format'
import type { RecentResearchEntry } from '../types/backend'

const STATUS_LABEL: Record<RecentResearchEntry['status'], string> = {
  COMPLETED: 'Completed',
  PARTIAL: 'Partial',
  FAILED: 'Failed',
  RUNNING: 'Running',
  PENDING: 'Pending',
}

function score(value: string | null): string {
  return toDisplayNumber(value, 0) ?? '—'
}

function ResearchRow({ entry }: { entry: RecentResearchEntry }) {
  return (
    <Link
      to={paths.stock(entry.ticker)}
      className="surface-card surface-card--interactive flex items-center justify-between gap-4 p-4"
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold">{entry.ticker}</span>
          {entry.company_name && (
            <span className="truncate text-sm text-[var(--color-text-faint)]">{entry.company_name}</span>
          )}
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-[var(--color-text-faint)]">
          <span>{STATUS_LABEL[entry.status]}</span>
          <span aria-hidden="true">·</span>
          <span>{formatDateTime(entry.completed_at) ?? entry.research_date}</span>
        </div>
      </div>
      <div className="metric-value shrink-0 text-lg">{score(entry.overall_score)}</div>
    </Link>
  )
}

/**
 * Global, cross-ticker research history -- every ticker anyone has ever
 * researched, newest first. Not "your" research: `ResearchRunRow` has no
 * `user_id` (see `app/db/models.py`), so this list is the same for every
 * viewer, signed in or not.
 */
export function ResearchHistoryPage() {
  const state = useAsync(() => fetchRecentResearch(50), [])

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 pb-32 pt-8 sm:px-6">
      <div>
        <h1 className="text-xl font-bold">Research</h1>
        <p className="support-text">
          Every ticker that has been researched, most recently updated first. This list is global, not filtered to
          your watchlist.
        </p>
      </div>

      <AsyncSection state={state} onRetry={state.reload} errorTitle="Could not load research history">
        {(entries) =>
          entries.length === 0 ? (
            <p className="support-text">
              Nothing has been researched yet. Search for a ticker and run research to start building this list.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {entries.map((entry) => (
                <ResearchRow key={`${entry.ticker}-${entry.research_run_id}`} entry={entry} />
              ))}
            </div>
          )
        }
      </AsyncSection>
    </main>
  )
}
