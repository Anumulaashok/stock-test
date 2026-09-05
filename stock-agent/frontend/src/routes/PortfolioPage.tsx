import { useAsync } from '../hooks/useAsync'
import { AsyncSection } from '../components/ui/AsyncSection'
import { SkeletonHoldingsTable } from '../components/ui/Skeleton'
import { deleteHolding, fetchPortfolioSummary } from '../api/portfolio'
import { AddHoldingForm } from '../features/portfolio/AddHoldingForm'
import { ContributorsDetractors } from '../features/portfolio/ContributorsDetractors'
import { HoldingsTable } from '../features/portfolio/HoldingsTable'
import { PositionSizeCalculator } from '../features/portfolio/PositionSizeCalculator'
import { holdingsToCsv } from '../features/portfolio/portfolioCsv'
import { PortfolioSummaryStats } from '../features/portfolio/PortfolioSummaryStats'
import { downloadCsv } from '../lib/csv'

/** Your holdings and their live performance -- extracted from
 * `DashboardPage.tsx`'s inlined portfolio section. Only renders behind
 * `RequireAuth` (see `routes.tsx`), so no anonymous state to handle. */
export function PortfolioPage() {
  const state = useAsync(() => fetchPortfolioSummary(), [])

  async function handleDelete(holdingId: string) {
    await deleteHolding(holdingId)
    state.reload()
  }

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 pb-32 pt-8 sm:px-6">
      <div>
        <h1 className="text-xl font-bold">Portfolio</h1>
        <p className="support-text">Your holdings and their unrealized gain, priced against the latest available quote.</p>
      </div>

      <AsyncSection
        state={state}
        onRetry={state.reload}
        errorTitle="Could not load your portfolio"
        skeleton={<SkeletonHoldingsTable />}
      >
        {(summary) => (
          <div className="flex flex-col gap-4">
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => downloadCsv('portfolio', holdingsToCsv(summary.holdings))}
                disabled={summary.holdings.length === 0}
                className="btn-secondary px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-60"
              >
                Export CSV
              </button>
            </div>
            <PortfolioSummaryStats summary={summary} />
            <HoldingsTable holdings={summary.holdings} onDelete={handleDelete} onChanged={state.reload} />
            <ContributorsDetractors holdings={summary.holdings} />
          </div>
        )}
      </AsyncSection>

      <AddHoldingForm onAdded={state.reload} />

      <PositionSizeCalculator />
    </main>
  )
}
