import { useState } from 'react'
import { analyzeTicker } from '../api/analysis'
import { ApiError } from '../api/client'
import type { CombinedAnalysisResult } from '../types/backend'
import { SearchBar } from '../components/SearchBar'
import { LoadingState } from '../components/LoadingState'
import { ErrorBanner } from '../components/ErrorBanner'
import { StatusBanner } from '../components/StatusBanner'
import { CompanyHeader } from '../components/CompanyHeader'
import { ScoreOverview } from '../components/ScoreOverview'
import { ValuationSection } from '../components/ValuationSection'
import { FinancialSection } from '../components/FinancialSection'
import { RiskSection } from '../components/RiskSection'
import { ResearchSection } from '../components/ResearchSection'
import { AnalystSection } from '../components/AnalystSection'
import { WarningsSection } from '../components/WarningsSection'

type ViewState =
  | { kind: 'idle' }
  | { kind: 'loading'; ticker: string }
  | { kind: 'error'; ticker: string; error: ApiError }
  | { kind: 'result'; ticker: string; result: CombinedAnalysisResult }

export function AnalysisPage() {
  const [state, setState] = useState<ViewState>({ kind: 'idle' })

  async function handleSearch(ticker: string) {
    setState({ kind: 'loading', ticker })
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

  const report = state.kind === 'result' ? state.result.report : null

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8">
      <div>
        <h1 className="text-xl font-semibold">Stock Research</h1>
        <p className="text-sm text-[var(--color-text-faint)]">
          Deterministic financial analysis, valuation, scoring, and AI-assisted commentary.
        </p>
      </div>

      <SearchBar onSubmit={handleSearch} disabled={state.kind === 'loading'} />

      {state.kind === 'loading' && <LoadingState ticker={state.ticker} />}
      {state.kind === 'error' && <ErrorBanner error={state.error} />}

      {state.kind === 'result' && report && (
        <div className="flex flex-col gap-8">
          <StatusBanner status={report.status} ticker={state.ticker} />
          <CompanyHeader report={report} />
          <ScoreOverview scoring={report.scoring} />
          <ValuationSection valuation={report.valuation} />
          <RiskSection risk={report.risk} />
          <AnalystSection analyst={report.analyst} />
          <FinancialSection financials={report.financials} />
          <ResearchSection research={report.research} />
          <WarningsSection warnings={report.warnings} />
        </div>
      )}

      {state.kind === 'result' && !report && (
        <p className="text-sm text-[var(--color-text-faint)]">
          The analysis completed but no structured report was returned.
        </p>
      )}
    </main>
  )
}
