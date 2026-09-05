import { MarketSnapshot } from '../features/home/MarketSnapshot'
import { TopOpportunities } from '../features/home/TopOpportunities'
import { RecentResearch } from '../features/home/RecentResearch'
import { WatchlistSummary } from '../features/home/WatchlistSummary'

/**
 * The public home page -- renders for both anonymous and authenticated
 * visitors. Each section fetches and fails independently (via
 * `useAsync`/`AsyncSection`) so one slow or broken data source never
 * takes the rest of the page down with it.
 */
export function HomePage() {
  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-8 px-4 pb-32 pt-8 sm:px-6 sm:pb-36">
      <header>
        <p className="section-heading">Deterministic Market Intelligence</p>
        <h1 className="mt-2 max-w-xl text-2xl font-bold leading-tight sm:text-3xl">
          Every score on this page traces back to a real, computed number
        </h1>
        <p className="mt-2 max-w-lg text-sm text-[var(--color-text-muted)]">
          Sector rankings and stock scores come straight from this app's own deterministic scoring engine -- no
          LLM-invented numbers, and no metric shown without a real source behind it.
        </p>
      </header>

      <MarketSnapshot />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-8 lg:col-span-2">
          <TopOpportunities />
          <RecentResearch />
        </div>
        <WatchlistSummary />
      </div>
    </main>
  )
}
