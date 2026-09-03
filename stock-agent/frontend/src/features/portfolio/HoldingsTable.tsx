import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { updateHolding } from '../../api/portfolio'
import { paths } from '../../routes/paths'
import { formatCurrency, toDisplayNumber } from '../../lib/format'
import type { HoldingWithMarketData, PriceStatus } from '../../types/backend'
import { toneClass, toneFor } from './toneFor'

const PRICE_STATUS_LABEL: Record<PriceStatus, string> = {
  live: 'live',
  delayed: 'delayed',
  stale: 'stale',
  unavailable: 'unavailable',
}

function parsePositive(value: string): boolean {
  const trimmed = value.trim()
  if (!trimmed) return false
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) && parsed > 0
}

function EditRow({
  holding,
  onDone,
}: {
  holding: HoldingWithMarketData
  onDone: () => void
}) {
  const [quantity, setQuantity] = useState(holding.quantity)
  const [averageCost, setAverageCost] = useState(holding.average_cost)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSave(event: FormEvent) {
    event.preventDefault()
    if (!parsePositive(quantity) || !parsePositive(averageCost)) {
      setError('Quantity and average cost must be positive numbers.')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      await updateHolding(holding.id, { quantity: quantity.trim(), average_cost: averageCost.trim() })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update holding.')
      setSubmitting(false)
    }
  }

  return (
    <tr className="border-t border-[var(--color-border)]">
      <td className="px-3 py-2 font-mono-nums">{holding.ticker}</td>
      <td className="px-3 py-2" colSpan={5}>
        <form onSubmit={handleSave} className="flex flex-wrap items-center gap-2">
          <label className="flex flex-col gap-1 text-xs">
            Quantity
            <input
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              type="number"
              step="any"
              className="input-field w-28 px-2 py-1 text-sm"
              aria-label={`Quantity for ${holding.ticker}`}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            Avg Cost
            <input
              value={averageCost}
              onChange={(e) => setAverageCost(e.target.value)}
              type="number"
              step="any"
              className="input-field w-28 px-2 py-1 text-sm"
              aria-label={`Average cost for ${holding.ticker}`}
            />
          </label>
          <button type="submit" disabled={submitting} className="btn-primary px-3 py-1.5 text-xs">
            {submitting ? 'Saving…' : 'Save'}
          </button>
          <button type="button" onClick={onDone} disabled={submitting} className="btn-secondary px-3 py-1.5 text-xs">
            Cancel
          </button>
          {error && <p className="w-full text-xs text-[var(--color-status-negative)]">{error}</p>}
        </form>
      </td>
    </tr>
  )
}

export function HoldingsTable({
  holdings,
  onDelete,
  onChanged,
}: {
  holdings: HoldingWithMarketData[]
  onDelete: (holdingId: string) => void
  /** Called after a successful inline edit -- the caller reloads the summary. */
  onChanged: () => void
}) {
  const [editingId, setEditingId] = useState<string | null>(null)

  if (holdings.length === 0) {
    return <p className="support-text">No holdings yet. Add one below to start tracking it.</p>
  }

  return (
    <div className="surface-card overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-xs text-[var(--color-text-faint)]" style={{ borderBottom: '1px solid var(--color-border)' }}>
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
          {holdings.map((holding) =>
            editingId === holding.id ? (
              <EditRow
                key={holding.id}
                holding={holding}
                onDone={() => {
                  setEditingId(null)
                  onChanged()
                }}
              />
            ) : (
              <tr key={holding.id} className="border-t border-[var(--color-border)]">
                <td className="px-3 py-2 font-mono-nums">
                  <Link to={paths.stock(holding.ticker)} className="text-[var(--color-accent-strong)] hover:underline">
                    {holding.ticker}
                  </Link>
                </td>
                <td className="px-3 py-2 font-mono-nums">{toDisplayNumber(holding.quantity, 4) ?? '—'}</td>
                <td className="px-3 py-2 font-mono-nums">{formatCurrency(holding.average_cost) ?? '—'}</td>
                <td className="px-3 py-2 font-mono-nums">
                  {formatCurrency(holding.current_price) ?? '—'}
                  <span className="ml-1 text-xs text-[var(--color-text-faint)]">
                    ({PRICE_STATUS_LABEL[holding.price_status]})
                  </span>
                </td>
                <td className="px-3 py-2 font-mono-nums">{formatCurrency(holding.market_value) ?? '—'}</td>
                <td className={`px-3 py-2 font-mono-nums ${toneClass(toneFor(holding.unrealized_gain))}`}>
                  {formatCurrency(holding.unrealized_gain) ?? '—'}
                  {holding.unrealized_gain_percent !== null && (
                    <span className="ml-1 text-xs">({toDisplayNumber(holding.unrealized_gain_percent, 2) ?? '—'}%)</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <div className="flex gap-3 text-xs">
                    <button
                      type="button"
                      onClick={() => setEditingId(holding.id)}
                      className="text-[var(--color-accent-strong)] underline"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(holding.id)}
                      className="text-[var(--color-status-negative)] underline"
                    >
                      Remove
                    </button>
                  </div>
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
    </div>
  )
}
