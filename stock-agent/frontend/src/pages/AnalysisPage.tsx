import { useEffect, useState } from 'react'
import { analyzeTicker } from '../api/analysis'
import { addWatchlistItem, fetchWatchlist, removeWatchlistItem } from '../api/portfolio'
import { ApiError } from '../api/client'
import type { CombinedAnalysisResult } from '../types/backend'
import { useAuth } from '../auth/AuthContext'
import { SearchBar } from '../components/SearchBar'
import { LoadingState } from '../components/LoadingState'
import { ErrorBanner } from '../components/ErrorBanner'
import { StatusBanner } from '../components/StatusBanner'
import { InvestmentSummary } from '../components/InvestmentSummary'
import { ScoreOverview } from '../components/ScoreOverview'
import { ValuationSection } from '../components/ValuationSection'
import { ForecastSection } from '../components/ForecastSection'
import { FinancialSection } from '../components/FinancialSection'
import { RiskSection } from '../components/RiskSection'
import { ResearchSection } from '../components/ResearchSection'
import { AnalystSection } from '../components/AnalystSection'
import { AskAssistantSection } from '../components/AskAssistantSection'
import { WarningsSection } from '../components/WarningsSection'
import { DataQualitySection } from '../components/DataQualitySection'
import { buildEvidenceValueMap } from '../lib/evidenceValues'

type ViewState =
  | { kind: 'idle' }
  | { kind: 'loading'; ticker: string }
  | { kind: 'error'; ticker: string; error: ApiError }
  | { kind: 'result'; ticker: string; result: CombinedAnalysisResult }

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

  async function handleSearch(ticker: string) {
    setState({ kind: 'loading', ticker })
    setInWatchlist(null)
    setWatchlistError(null)
    try {
      const result = await analyzeTicker(ticker)
      setState({ kind: 'result', ticker, result })
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

  const report = state.kind === 'result' ? state.result.report : null
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
    <main className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-10 sm:px-6">
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
          <StatusBanner status={report.status} ticker={state.ticker} />
          <InvestmentSummary
            report={report}
            authStatus={authStatus}
            inWatchlist={inWatchlist}
            watchlistPending={watchlistPending}
            watchlistError={watchlistError}
            onToggleWatchlist={handleToggleWatchlist}
          />
          <ScoreOverview scoring={report.scoring} />
          <ValuationSection valuation={report.valuation} />
          <ForecastSection forecast={report.forecast} />
          <RiskSection risk={report.risk} />
          <AnalystSection analyst={report.analyst} evidenceValues={buildEvidenceValueMap(report)} />
          <FinancialSection financials={report.financials} />
          <ResearchSection research={report.research} />
          <DataQualitySection report={report} />
          <WarningsSection warnings={report.warnings} />
          <AskAssistantSection ticker={state.ticker} />
        </div>
      )}

      {state.kind === 'result' && !report && (
        <p className="text-center text-sm text-[var(--color-text-faint)]">
          The analysis completed but no structured report was returned.
        </p>
      )}
    </main>
  )
}
