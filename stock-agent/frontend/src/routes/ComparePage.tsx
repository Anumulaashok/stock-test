import { useSearchParams } from 'react-router-dom'
import { fetchLatestResearch } from '../api/research'
import { useAsync } from '../hooks/useAsync'
import { AsyncSection } from '../components/ui/AsyncSection'
import { CompareTable } from '../features/compare/CompareTable'
import { buildFinancialMetricRows, buildRiskRows, buildSummaryRows, buildValuationRows } from '../features/compare/compareRows'
import type { InvestmentResearchReport } from '../types/backend'

const MAX_TICKERS = 4

function parseTickers(raw: string | null): string[] {
  if (!raw) return []
  return Array.from(new Set(raw.split(',').map((t) => t.trim().toUpperCase()).filter(Boolean))).slice(0, MAX_TICKERS)
}

/**
 * 2-4 tickers, aligned metric rows -- never stacked detail pages. Every
 * cell is a value the backend already returned; "Unavailable" for a
 * ticker never researched or missing that metric, never blank/zero/
 * borrowed from a neighboring column. Best/worst emphasis only where
 * an unambiguous "higher is better" convention already exists
 * elsewhere in this app (score, valuation upside) -- see
 * compareRows.ts for why raw financial metrics don't get it.
 */
export function ComparePage() {
  const [searchParams] = useSearchParams()
  const tickers = parseTickers(searchParams.get('tickers'))

  const state = useAsync(
    () => Promise.all(tickers.map((t) => fetchLatestResearch(t).then((r) => r?.result.report ?? null))),
    [tickers.join(',')],
  )

  if (tickers.length < 2) {
    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-4 px-4 pt-8 text-center">
        <p className="support-text">Add at least two tickers to compare, e.g. <code>/compare?tickers=RELIANCE,TCS</code>.</p>
      </main>
    )
  }

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 px-4 pb-32 pt-8">
      <div>
        <h1 className="text-xl font-semibold">Compare</h1>
        <p className="support-text">{tickers.join(' vs. ')}</p>
      </div>

      <AsyncSection state={state} onRetry={state.reload} errorTitle="Could not load one or more of these reports">
        {(reports: (InvestmentResearchReport | null)[]) => (
          <div className="flex flex-col gap-4">
            <CompareTable title="Summary" rows={buildSummaryRows(reports, tickers)} tickers={tickers} />
            <CompareTable title="Valuation" rows={buildValuationRows(reports, tickers)} tickers={tickers} />
            <CompareTable title="Financial metrics" rows={buildFinancialMetricRows(reports, tickers)} tickers={tickers} />
            <CompareTable title="Risk" rows={buildRiskRows(reports, tickers)} tickers={tickers} />
            {reports.every((r) => r === null) && (
              <p className="support-text text-center">None of these tickers have been researched yet.</p>
            )}
          </div>
        )}
      </AsyncSection>
    </main>
  )
}
