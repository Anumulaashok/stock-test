import { MarketSnapshot } from '../features/home/MarketSnapshot'
import { TopOpportunities } from '../features/home/TopOpportunities'
import { RecentResearch } from '../features/home/RecentResearch'
import { WatchlistSummary } from '../features/home/WatchlistSummary'
import { formatDate } from '../lib/format'

/**
 * The public home page -- renders for both anonymous and authenticated
 * visitors. Each section fetches and fails independently (via
 * `useAsync`/`AsyncSection`) so one slow or broken data source never
 * takes the rest of the page down with it.
 */
export function HomePage() {
  const today = formatDate(new Date().toISOString())

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-8 px-4 pb-32 pt-8 sm:px-6 sm:pb-36">
      <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div>
          <p className="section-heading">Market Intelligence</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">Today's desk</h1>
        </div>
        {today && <span className="font-mono-nums pb-0.5 text-xs text-[var(--color-text-faint)]">{today}</span>}
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
