import { Link } from 'react-router-dom'
import { useAsync } from '../../hooks/useAsync'
import { AsyncSection } from '../../components/ui/AsyncSection'
import { fetchRecentResearch } from '../../api/research'
import { paths } from '../../routes/paths'
import { toDisplayNumber, formatDate } from '../../lib/format'
import type { RecentResearchEntry } from '../../types/backend'

const PREVIEW_LIMIT = 8

function score(value: string | null): string {
  return toDisplayNumber(value, 0) ?? '—'
}

function ResearchCard({ entry }: { entry: RecentResearchEntry }) {
  return (
    <Link
      to={paths.stock(entry.ticker)}
      className="surface-card surface-card--interactive flex min-w-[160px] flex-col gap-1.5 p-3.5"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-semibold">{entry.ticker}</span>
        <span className="metric-value text-base">{score(entry.overall_score)}</span>
      </div>
      <span className="truncate text-[11px] text-[var(--color-text-faint)]">{entry.company_name ?? '—'}</span>
      <span className="text-[10px] text-[var(--color-text-faint)]">
        {formatDate(entry.research_date) ?? entry.research_date}
      </span>
    </Link>
  )
}

/**
 * The most recently researched tickers, global (research has no
 * `user_id` -- see `app/db/models.py` -- so this is the same list for
 * every viewer, signed in or not). Backed by `GET
 * /api/v1/research/recent`, one request regardless of how many tickers
 * exist -- replaces the old `IntelligencePage` pattern of fetching the
 * watchlist, then one `fetchLatestResearch` call per ticker.
 */
export function RecentResearch() {
  const state = useAsync(() => fetchRecentResearch(PREVIEW_LIMIT), [])

  return (
    <section className="flex flex-col gap-4" aria-labelledby="recent-research-heading">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 id="recent-research-heading" className="section-heading">
            Recent Research
          </h2>
          <p className="support-text">The most recently updated research snapshots across every ticker.</p>
        </div>
        <Link to={paths.research()} className="text-xs font-medium text-[var(--color-accent-strong)] hover:underline">
          View all
        </Link>
      </div>

      <AsyncSection state={state} onRetry={state.reload} errorTitle="Could not load research history">
        {(entries) =>
          entries.length === 0 ? (
            <p className="support-text">Research history will appear here once someone researches a stock.</p>
          ) : (
            <div className="flex flex-wrap gap-3">
              {entries.map((entry) => (
                <ResearchCard key={entry.ticker} entry={entry} />
              ))}
            </div>
          )
        }
      </AsyncSection>
    </section>
  )
}
