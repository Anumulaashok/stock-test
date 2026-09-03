import { useEffect, useState } from 'react'
import { fetchLatestResearch, fetchResearchRun, runResearch } from '../api/research'
import { addWatchlistItem, fetchWatchlist, removeWatchlistItem } from '../api/portfolio'
import { ApiError } from '../api/client'
import type { ResearchRunResult } from '../types/backend'
import { useAuth } from '../auth/AuthContext'
import { SearchBar } from '../components/SearchBar'
import { LoadingState } from '../components/LoadingState'
import { ErrorBanner } from '../components/ErrorBanner'
import { StatusBanner } from '../components/StatusBanner'
import { ValuationSection } from '../components/ValuationSection'
import { ForecastSection } from '../components/ForecastSection'
import { FinancialSection } from '../components/FinancialSection'
import { ResearchSection } from '../components/ResearchSection'
import { ResearchSnapshotBanner } from '../components/ResearchSnapshotBanner'
import { ResearchHistorySection } from '../components/ResearchHistorySection'
import { AnalystSection } from '../components/AnalystSection'
import { StickyAskAssistant } from '../components/StickyAskAssistant'
import { WarningsSection } from '../components/WarningsSection'
import { DataQualitySection } from '../components/DataQualitySection'
import { buildEvidenceValueMap } from '../lib/evidenceValues'
import { StockHeader } from '../components/stock/StockHeader'
import { InvestmentVerdict } from '../components/stock/InvestmentVerdict'
import { ScoreBreakdown } from '../components/stock/ScoreBreakdown'
import { WhyThisScore } from '../components/stock/WhyThisScore'
import { InvestorSummary } from '../components/stock/InvestorSummary'
import { RiskOverview } from '../components/stock/RiskOverview'

type ViewState =
  | { kind: 'idle' }
  | { kind: 'loading'; ticker: string }
  | { kind: 'error'; ticker: string; error: ApiError }
  | { kind: 'result'; ticker: string; run: ResearchRunResult }

interface AnalysisPageProps {
  /** Set when navigating in from elsewhere (e.g. the dashboard's search
   * or a watchlist item) with a ticker already chosen. */
  initialTicker?: string
}

export function AnalysisPage({ initialTicker }: AnalysisPageProps = {}) {
  const [state, setState] = useState<ViewState>({ kind: 'idle' })
  const { status: authStatus } = useAuth()

  // Watchlist membership for whatever ticker is currently on screen --
  // `null` means "not yet known" (still loading, or not authenticated),
  // never a guessed default.
  const [inWatchlist, setInWatchlist] = useState<boolean | null>(null)
  const [watchlistPending, setWatchlistPending] = useState(false)
  const [watchlistError, setWatchlistError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  async function handleSearch(ticker: string, forceRefresh = false) {
    setState({ kind: 'loading', ticker })
    setInWatchlist(null)
    setWatchlistError(null)
    try {
      // A plain search always surfaces the latest already-computed
      // result (any date, normal or force-refresh) instead of kicking
      // off a redundant new run -- only compute when nothing exists yet.
      const run = forceRefresh
        ? await runResearch(ticker, true)
        : (await fetchLatestResearch(ticker)) ?? (await runResearch(ticker, false))
      setState({ kind: 'result', ticker, run })
    } catch (error) {
      setState({
        kind: 'error',
        ticker,
        error: error instanceof ApiError ? error : new ApiError('Unexpected error.', 'network'),
      })
    }
  }

  useEffect(() => {
    if (initialTicker) void handleSearch(initialTicker)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialTicker])

  async function handleRefresh(forceRefresh: boolean) {
    if (state.kind !== 'result') return
    const ticker = state.ticker
    setRefreshing(true)
    try {
      const run = await runResearch(ticker, forceRefresh)
      setState({ kind: 'result', ticker, run })
    } catch (error) {
      setState({
        kind: 'error',
        ticker,
        error: error instanceof ApiError ? error : new ApiError('Unexpected error.', 'network'),
      })
    } finally {
      setRefreshing(false)
    }
  }

  async function handleSelectHistoryRun(researchRunId: string) {
    if (state.kind !== 'result') return
    const ticker = state.ticker
    setRefreshing(true)
    try {
      const run = await fetchResearchRun(ticker, researchRunId)
      setState({ kind: 'result', ticker, run })
    } catch (error) {
      setState({
        kind: 'error',
        ticker,
        error: error instanceof ApiError ? error : new ApiError('Unexpected error.', 'network'),
      })
    } finally {
      setRefreshing(false)
    }
  }

  const report = state.kind === 'result' ? state.run.result.report : null
  const resolvedTicker = state.kind === 'result' ? state.ticker : null

  // Look up whether the currently-analyzed ticker is already saved --
  // uses the real `/api/v1/watchlist` endpoint, never a local fake list.
  useEffect(() => {
    if (authStatus !== 'authenticated' || !resolvedTicker) {
      setInWatchlist(null)
      return
    }
    let cancelled = false
    fetchWatchlist()
      .then((items) => {
        if (cancelled) return
        setInWatchlist(items.some((item) => item.ticker.toUpperCase() === resolvedTicker.toUpperCase()))
      })
      .catch(() => {
        if (!cancelled) setInWatchlist(null)
      })
    return () => {
      cancelled = true
    }
  }, [authStatus, resolvedTicker])

  async function handleToggleWatchlist() {
    if (!resolvedTicker || inWatchlist === null) return
    setWatchlistPending(true)
    setWatchlistError(null)
    const wasInWatchlist = inWatchlist
    try {
      if (wasInWatchlist) {
        await removeWatchlistItem(resolvedTicker)
      } else {
        await addWatchlistItem(resolvedTicker)
      }
      setInWatchlist(!wasInWatchlist)
    } catch (error) {
      setWatchlistError(error instanceof ApiError ? error.message : 'Could not update your watchlist.')
    } finally {
      setWatchlistPending(false)
    }
  }

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-8 px-4 pb-32 pt-10 sm:px-6 sm:pb-36">
      <div className="animate-fade-in-up flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Stock Research</h1>
        <p className="max-w-md text-sm text-[var(--color-text-faint)]">
          Deterministic financial analysis, valuation, scoring, and AI-assisted commentary — search a ticker or
          company name to begin.
        </p>
      </div>

      <div className="animate-fade-in-up flex justify-center" style={{ animationDelay: '40ms' }}>
        <SearchBar onSubmit={handleSearch} disabled={state.kind === 'loading'} />
      </div>

      {state.kind === 'loading' && <LoadingState ticker={state.ticker} />}
      {state.kind === 'error' && (
        <div className="animate-fade-in-up">
          <ErrorBanner error={state.error} />
        </div>
      )}

      {state.kind === 'result' && report && (
        <div className="animate-fade-in-up flex flex-col gap-10">
          <ResearchSnapshotBanner
            run={state.run}
            refreshing={refreshing}
            onRefresh={() => handleRefresh(false)}
            onForceRefresh={() => handleRefresh(true)}
          />
          <StatusBanner status={report.status} ticker={state.ticker} />

          {/* Decision -> explanation -> evidence -> detail (see the plan's
              §33 flow): verdict and header first, raw sections last. */}
          <StockHeader
            company={report.company}
            market={report.market}
            authStatus={authStatus}
            inWatchlist={inWatchlist}
            watchlistPending={watchlistPending}
            watchlistError={watchlistError}
            onToggleWatchlist={handleToggleWatchlist}
          />
          <InvestmentVerdict summary={report.summary} />
          <ScoreBreakdown scoring={report.scoring} />
          <WhyThisScore report={report} />
          <InvestorSummary report={report} />
          <RiskOverview risk={report.risk} />
          <ValuationSection valuation={report.valuation} />
          <FinancialSection financials={report.financials} />
          <ForecastSection forecast={report.forecast} />
          <ResearchSection research={report.research} />
          <AnalystSection analyst={report.analyst} evidenceValues={buildEvidenceValueMap(report)} />
          <DataQualitySection report={report} />
          <WarningsSection warnings={report.warnings} />
          <ResearchHistorySection ticker={state.ticker} onSelectRun={handleSelectHistoryRun} />
        </div>
      )}

      {state.kind === 'result' && !report && (
        <p className="text-center text-sm text-[var(--color-text-faint)]">
          The analysis completed but no structured report was returned.
        </p>
      )}

      <StickyAskAssistant ticker={state.kind === 'result' ? state.ticker : null} />
    </main>
  )
}
