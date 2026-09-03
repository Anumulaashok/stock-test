import { Navigate, Outlet, useParams, useSearchParams } from 'react-router-dom'
import { StockReportProvider, useStockReportState } from '../stock/StockReportContext'
import { useWatchlistMembership } from '../hooks/useWatchlistMembership'
import { paths } from '../routes/paths'
import { LoadingState } from '../components/LoadingState'
import { ErrorBanner } from '../components/ErrorBanner'
import { StatusBanner } from '../components/StatusBanner'
import { EmptyState } from '../components/SectionHeader'
import { ResearchSnapshotBanner } from '../components/ResearchSnapshotBanner'
import { StockHeader } from '../components/stock/StockHeader'
import { StockTabBar } from './StockTabBar'

/**
 * The `/stock/:ticker` layout route. Fetches `CombinedAnalysisResult`
 * exactly once via `StockReportProvider` (`key={ticker}` so state resets
 * per ticker, not per tab switch) and only mounts `<Outlet/>` -- the
 * eight tabs -- once the report is `ready`. Loading/error/empty states
 * are rendered here, once, instead of duplicated in every tab.
 */
export function StockLayout() {
  const { ticker: rawTicker = '' } = useParams<{ ticker: string }>()
  const [searchParams] = useSearchParams()
  const runId = searchParams.get('run') ?? undefined
  const ticker = rawTicker.toUpperCase()

  if (rawTicker !== ticker) {
    return <Navigate replace to={{ pathname: paths.stock(ticker), search: window.location.search }} />
  }

  return (
    <StockReportProvider key={ticker} ticker={ticker} researchRunId={runId}>
      <StockLayoutInner ticker={ticker} />
    </StockReportProvider>
  )
}

function StockLayoutInner({ ticker }: { ticker: string }) {
  const { state, refreshing, runNew, reload } = useStockReportState()
  const watchlist = useWatchlistMembership(ticker)

  if (state.status === 'loading') {
    return (
      <main className="mx-auto flex max-w-5xl flex-col gap-8 px-4 pb-32 pt-10 sm:px-6 sm:pb-36">
        <LoadingState ticker={ticker} />
      </main>
    )
  }

  if (state.status === 'error') {
    // A 409 means another request is already researching this exact
    // ticker+day (see `ResearchInProgressError` -- single-process
    // DB-level single-flight, not a distributed lock). That request will
    // finish shortly and its result becomes readable via a plain GET, so
    // this gets its own retry affordance rather than a dead-end banner.
    if (state.error.status === 409) {
      return (
        <main className="mx-auto flex max-w-5xl flex-col items-center gap-4 px-4 pb-32 pt-16 text-center sm:px-6 sm:pb-36">
          <p className="font-medium text-[var(--color-text-muted)]">Research is already running for {ticker}</p>
          <p className="support-text max-w-sm">
            Another request started analyzing {ticker} moments ago. It should finish shortly -- check again in a bit.
          </p>
          <button type="button" onClick={() => void reload()} disabled={refreshing} className="btn-primary px-4 py-2">
            {refreshing ? 'Checking…' : 'Check again'}
          </button>
        </main>
      )
    }
    return (
      <main className="mx-auto flex max-w-5xl flex-col gap-8 px-4 pb-32 pt-10 sm:px-6 sm:pb-36">
        <ErrorBanner error={state.error} />
      </main>
    )
  }

  if (state.status === 'empty') {
    return (
      <main className="mx-auto flex max-w-5xl flex-col items-center gap-6 px-4 pb-32 pt-16 sm:px-6 sm:pb-36">
        <EmptyState title={`${ticker} hasn't been researched yet`} reason="Run research to generate a report." />
        <button type="button" onClick={() => void runNew()} disabled={refreshing} className="btn-primary px-4 py-2">
          {refreshing ? 'Running research…' : 'Run research'}
        </button>
      </main>
    )
  }

  const { run, report } = state

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 pb-32 pt-6 sm:px-6 sm:pb-36">
      <ResearchSnapshotBanner
        run={run}
        refreshing={refreshing}
        onRefresh={() => void reload()}
        onForceRefresh={() => void runNew({ force: true })}
      />
      <StatusBanner status={report.status} ticker={ticker} />
      <StockHeader
        company={report.company}
        market={report.market}
        authStatus={watchlist.authStatus}
        inWatchlist={watchlist.inWatchlist}
        watchlistPending={watchlist.pending}
        watchlistError={watchlist.error}
        onToggleWatchlist={() => void watchlist.toggle()}
      />
      <StockTabBar ticker={ticker} />
      <div className="animate-fade-in-up flex flex-col gap-10">
        <Outlet />
      </div>
    </main>
  )
}
