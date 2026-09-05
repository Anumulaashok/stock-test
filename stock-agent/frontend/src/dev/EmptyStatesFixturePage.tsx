import { HoldingsTable } from '../features/portfolio/HoldingsTable'
import { WatchlistList } from '../features/watchlist/WatchlistList'
import { AddHoldingForm } from '../features/portfolio/AddHoldingForm'
import { AddTickerForm } from '../features/watchlist/AddTickerForm'

// Dev-only gallery for the Wave 7 one-click empty states (no network calls).

export function EmptyStatesFixturePage() {
  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-4 py-10">
      <div>
        <h1 className="text-lg font-bold">Empty States Fixture Gallery (dev only)</h1>
        <p className="support-text text-xs">Not reachable in production.</p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--color-text-muted)]">Watchlist -- empty</h2>
        <AddTickerForm onAdd={async () => {}} />
        <WatchlistList items={[]} onRemove={async () => {}} />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--color-text-muted)]">Portfolio -- empty</h2>
        <HoldingsTable holdings={[]} onDelete={() => {}} onChanged={() => {}} />
        <AddHoldingForm onAdded={() => {}} />
      </section>
    </main>
  )
}
