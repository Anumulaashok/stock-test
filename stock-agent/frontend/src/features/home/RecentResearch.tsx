import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useAsync } from '../../hooks/useAsync'
import { AsyncSection } from '../../components/ui/AsyncSection'
import { ErrorState } from '../../components/ui/ErrorState'
import { SkeletonRows } from '../../components/ui/Skeleton'
import { fetchWatchlist } from '../../api/portfolio'
import { fetchLatestResearch } from '../../api/research'
import { paths } from '../../routes/paths'
import { toDisplayNumber, formatDate } from '../../lib/format'
import type { ResearchRunResult } from '../../types/backend'

/**
 * Deliberately NOT the old `IntelligencePage` pattern (fetch the whole
 * watchlist, then fan out one `fetchLatestResearch` call per ticker for
 * every viewer). There is no `GET /api/v1/research/recent` endpoint yet
 * (a separate workstream owns that), so this stays honestly minimal:
 * the fan-out only ever runs for a small watchlist (<= 3 tickers) --
 * otherwise it links to `/research` instead of hammering the API.
 */
const RESEARCH_FANOUT_LIMIT = 3

function score(value: string | null | undefined): string {
  return toDisplayNumber(value ?? null, 0) ?? '—'
}

function ResearchCard({ result }: { result: ResearchRunResult }) {
  const overallScore = result.result.report?.scoring?.overall_score ?? null
  return (
    <Link
      to={paths.stock(result.ticker)}
      className="surface-card surface-card--interactive flex min-w-[160px] flex-col gap-1.5 p-3.5"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-semibold">{result.ticker}</span>
        <span className="metric-value text-base">{score(overallScore)}</span>
      </div>
      <span className="truncate text-[11px] text-[var(--color-text-faint)]">{result.result.company.name}</span>
      <span className="text-[10px] text-[var(--color-text-faint)]">
        {formatDate(result.research_date) ?? result.research_date}
      </span>
    </Link>
  )
}

function AuthenticatedRecentResearch() {
  const watchlistState = useAsync(fetchWatchlist, [])
  const tickers = watchlistState.status === 'success' ? watchlistState.data.map((item) => item.ticker) : []
  const withinFanoutLimit = tickers.length > 0 && tickers.length <= RESEARCH_FANOUT_LIMIT

  const researchState = useAsync(
    () => Promise.all(tickers.map((ticker) => fetchLatestResearch(ticker))),
    [tickers.join(',')],
    { enabled: watchlistState.status === 'success' && withinFanoutLimit },
  )

  if (watchlistState.status === 'idle' || watchlistState.status === 'loading') {
    return <SkeletonRows count={3} />
  }
  if (watchlistState.status === 'error') {
    return (
      <ErrorState title="Could not load research history" error={watchlistState.error} onRetry={watchlistState.reload} />
    )
  }
  if (tickers.length === 0) {
    return <p className="support-text">Research history will appear here once you've researched a stock.</p>
  }
  if (!withinFanoutLimit) {
    return (
      <Link to={paths.research()} className="text-sm font-medium text-[var(--color-accent-strong)] hover:underline">
        View research history →
      </Link>
    )
  }

  return (
    <AsyncSection state={researchState} onRetry={researchState.reload} errorTitle="Could not load research history">
      {(results) => {
        const completed = results.filter((r): r is ResearchRunResult => r !== null)
        if (completed.length === 0) {
          return <p className="support-text">Research history will appear here once you've researched a stock.</p>
        }
        return (
          <div className="flex flex-wrap gap-3">
            {completed.map((result) => (
              <ResearchCard key={result.ticker} result={result} />
            ))}
          </div>
        )
      }}
    </AsyncSection>
  )
}

export function RecentResearch() {
  const { status } = useAuth()

  return (
    <section className="flex flex-col gap-4" aria-labelledby="recent-research-heading">
      <div>
        <h2 id="recent-research-heading" className="section-heading">
          Recent Research
        </h2>
        <p className="support-text">The latest saved research snapshot for tickers on your watchlist.</p>
      </div>

      {status === 'checking' && <SkeletonRows count={3} />}

      {status === 'anonymous' && (
        <p className="support-text">
          <Link to={paths.login()} className="font-medium text-[var(--color-accent-strong)] hover:underline">
            Sign in
          </Link>{' '}
          and research a stock to build your history here.
        </p>
      )}

      {status === 'authenticated' && <AuthenticatedRecentResearch />}
    </section>
  )
}
