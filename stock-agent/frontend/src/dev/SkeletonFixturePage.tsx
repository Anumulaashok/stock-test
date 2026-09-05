import { SkeletonHoldingsTable, SkeletonWatchlistRows } from '../components/ui/Skeleton'

// Dev-only gallery for the Wave 7 layout-matching skeletons.

export function SkeletonFixturePage() {
  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-4 py-10">
      <div>
        <h1 className="text-lg font-bold">Skeleton Fixture Gallery (dev only)</h1>
      </div>
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--color-text-muted)]">Watchlist skeleton</h2>
        <SkeletonWatchlistRows />
      </section>
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--color-text-muted)]">Holdings table skeleton</h2>
        <SkeletonHoldingsTable />
      </section>
    </main>
  )
}
