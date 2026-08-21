import { useEffect, useState, type FormEvent } from 'react'
import {
  addHolding,
  addWatchlistItem,
  deleteHolding,
  fetchPortfolioSummary,
  fetchWatchlist,
  removeWatchlistItem,
} from '../api/portfolio'
import { ApiError } from '../api/client'
import { toDisplayNumber } from '../lib/format'
import type { PortfolioSummary, WatchlistItem } from '../types/backend'
import { SearchBar } from '../components/SearchBar'

interface DashboardPageProps {
  /** Reuses the existing analysis flow -- searching from the dashboard
   * jumps straight to the research terminal for that ticker. */
  onAnalyze: (ticker: string) => void
}

function money(value: string | null): string {
  const formatted = toDisplayNumber(value, 2)
  return formatted === null ? '—' : `$${formatted}`
}

function percent(value: string | null): string {
  const formatted = toDisplayNumber(value, 2)
  return formatted === null ? '—' : `${formatted}%`
}

export function DashboardPage({ onAnalyze }: DashboardPageProps) {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  async function refresh() {
    try {
      const [summaryResult, watchlistResult] = await Promise.all([fetchPortfolioSummary(), fetchWatchlist()])
      setSummary(summaryResult)
      setWatchlist(watchlistResult)
      setLoadError(null)
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : 'Could not load your portfolio.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleAddHolding(ticker: string, quantity: string, averageCost: string) {
    await addHolding(ticker, quantity, averageCost)
    await refresh()
  }

  async function handleDeleteHolding(holdingId: string) {
    await deleteHolding(holdingId)
    await refresh()
  }

  async function handleAddWatchlistItem(ticker: string) {
    await addWatchlistItem(ticker)
    await refresh()
  }

  async function handleRemoveWatchlistItem(ticker: string) {
    await removeWatchlistItem(ticker)
    await refresh()
  }

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-8">
      <div>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-sm text-[var(--color-text-faint)]">Your portfolio, watchlist, and research search.</p>
      </div>

      <SearchBar onSubmit={onAnalyze} disabled={false} />

      {loading && <p className="text-sm text-[var(--color-text-faint)]">Loading…</p>}
      {loadError && <p className="text-sm text-[var(--color-status-negative)]">{loadError}</p>}

      {summary && (
        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold">Portfolio</h2>

          <div className="grid grid-cols-2 gap-4 rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-4 sm:grid-cols-4">
            <Stat label="Invested" value={money(summary.invested_capital)} />
            <Stat label="Value" value={money(summary.portfolio_value)} />
            <Stat
              label="Gain / Loss"
              value={money(summary.unrealized_gain)}
              tone={toneFor(summary.unrealized_gain)}
            />
            <Stat
              label="Gain / Loss %"
              value={percent(summary.unrealized_gain_percent)}
              tone={toneFor(summary.unrealized_gain_percent)}
            />
          </div>

          {summary.warnings.length > 0 && (
            <ul className="list-inside list-disc text-xs text-[var(--color-text-faint)]">
              {summary.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}

          <HoldingsTable holdings={summary.holdings} onDelete={handleDeleteHolding} />
          <AddHoldingForm onAdd={handleAddHolding} />
        </section>
      )}

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">Watchlist</h2>
        <WatchlistTable items={watchlist} onRemove={handleRemoveWatchlistItem} onAnalyze={onAnalyze} />
        <AddWatchlistForm onAdd={handleAddWatchlistItem} />
      </section>
    </main>
  )
}

function toneFor(value: string | null): 'positive' | 'negative' | undefined {
  if (value === null) return undefined
  const parsed = Number(value)
  if (Number.isNaN(parsed)) return undefined
  return parsed >= 0 ? 'positive' : 'negative'
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'positive' | 'negative' }) {
  const color =
    tone === 'positive'
      ? 'text-[var(--color-status-positive)]'
      : tone === 'negative'
        ? 'text-[var(--color-status-negative)]'
        : 'text-[var(--color-text)]'
  return (
    <div>
      <div className="text-xs text-[var(--color-text-faint)]">{label}</div>
      <div className={`font-mono-nums text-lg font-semibold ${color}`}>{value}</div>
    </div>
  )
}

function HoldingsTable({
  holdings,
  onDelete,
}: {
  holdings: PortfolioSummary['holdings']
  onDelete: (holdingId: string) => void
}) {
  if (holdings.length === 0) {
    return <p className="text-sm text-[var(--color-text-faint)]">No holdings yet.</p>
  }
  return (
    <div className="overflow-x-auto rounded border border-[var(--color-border)]">
      <table className="w-full text-sm">
        <thead className="bg-[var(--color-surface-raised)] text-left text-xs text-[var(--color-text-faint)]">
          <tr>
            <th className="px-3 py-2">Ticker</th>
            <th className="px-3 py-2">Quantity</th>
            <th className="px-3 py-2">Avg Cost</th>
            <th className="px-3 py-2">Price</th>
            <th className="px-3 py-2">Value</th>
            <th className="px-3 py-2">Gain / Loss</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {holdings.map((holding) => (
            <tr key={holding.id} className="border-t border-[var(--color-border)]">
              <td className="px-3 py-2 font-mono-nums">{holding.ticker}</td>
              <td className="px-3 py-2 font-mono-nums">{toDisplayNumber(holding.quantity, 4) ?? '—'}</td>
              <td className="px-3 py-2 font-mono-nums">{money(holding.average_cost)}</td>
              <td className="px-3 py-2 font-mono-nums">
                {money(holding.current_price)}
                {holding.price_status !== 'unavailable' && (
                  <span className="ml-1 text-xs text-[var(--color-text-faint)]">({holding.price_status})</span>
                )}
              </td>
              <td className="px-3 py-2 font-mono-nums">{money(holding.market_value)}</td>
              <td className={`px-3 py-2 font-mono-nums ${toneFor(holding.unrealized_gain) === 'positive' ? 'text-[var(--color-status-positive)]' : toneFor(holding.unrealized_gain) === 'negative' ? 'text-[var(--color-status-negative)]' : ''}`}>
                {money(holding.unrealized_gain)}
              </td>
              <td className="px-3 py-2">
                <button
                  type="button"
                  onClick={() => onDelete(holding.id)}
                  className="text-xs text-[var(--color-status-negative)] underline"
                >
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AddHoldingForm({ onAdd }: { onAdd: (ticker: string, quantity: string, averageCost: string) => Promise<void> }) {
  const [ticker, setTicker] = useState('')
  const [quantity, setQuantity] = useState('')
  const [averageCost, setAverageCost] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await onAdd(ticker, quantity, averageCost)
      setTicker('')
      setQuantity('')
      setAverageCost('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add holding.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-2">
      <label className="flex flex-col gap-1 text-xs">
        Ticker
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          required
          className="w-24 rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-1"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs">
        Quantity
        <input
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          type="number"
          step="any"
          min="0"
          required
          className="w-28 rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-1"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs">
        Avg Cost
        <input
          value={averageCost}
          onChange={(e) => setAverageCost(e.target.value)}
          type="number"
          step="any"
          min="0"
          required
          className="w-28 rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-1"
        />
      </label>
      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-[var(--color-accent)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
      >
        Add holding
      </button>
      {error && <p className="w-full text-xs text-[var(--color-status-negative)]">{error}</p>}
    </form>
  )
}

function WatchlistTable({
  items,
  onRemove,
  onAnalyze,
}: {
  items: WatchlistItem[]
  onRemove: (ticker: string) => void
  onAnalyze: (ticker: string) => void
}) {
  if (items.length === 0) {
    return <p className="text-sm text-[var(--color-text-faint)]">Your watchlist is empty.</p>
  }
  return (
    <ul className="flex flex-col gap-1">
      {items.map((item) => (
        <li
          key={item.ticker}
          className="flex items-center justify-between rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2"
        >
          <span className="font-mono-nums">{item.ticker}</span>
          <div className="flex gap-3 text-xs">
            <button type="button" onClick={() => onAnalyze(item.ticker)} className="text-[var(--color-accent)] underline">
              Analyze
            </button>
            <button
              type="button"
              onClick={() => onRemove(item.ticker)}
              className="text-[var(--color-status-negative)] underline"
            >
              Remove
            </button>
          </div>
        </li>
      ))}
    </ul>
  )
}

function AddWatchlistForm({ onAdd }: { onAdd: (ticker: string) => Promise<void> }) {
  const [ticker, setTicker] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await onAdd(ticker)
      setTicker('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add to watchlist.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-2">
      <label className="flex flex-col gap-1 text-xs">
        Ticker
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          required
          className="w-24 rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-1"
        />
      </label>
      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-[var(--color-accent)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
      >
        Add to watchlist
      </button>
      {error && <p className="text-xs text-[var(--color-status-negative)]">{error}</p>}
    </form>
  )
}
