import { Link } from 'react-router-dom'
import { formatCurrency, toDisplayNumber } from '../../lib/format'
import { paths } from '../../routes/paths'
import { topContributors, topDetractors } from './topContributorsDetractors'
import type { HoldingWithMarketData } from '../../types/backend'

function HoldingRow({ holding, tone }: { holding: HoldingWithMarketData; tone: 'positive' | 'negative' }) {
  return (
    <li className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
      <Link to={paths.stock(holding.ticker)} className="font-mono-nums font-semibold text-[var(--color-accent-strong)] hover:underline">
        {holding.ticker}
      </Link>
      <div className="text-right">
        <div className={`font-mono-nums ${tone === 'positive' ? 'text-[var(--color-status-positive)]' : 'text-[var(--color-status-negative)]'}`}>
          {toDisplayNumber(holding.unrealized_gain_percent, 2) ?? '—'}%
        </div>
        <div className="text-xs text-[var(--color-text-faint)]">{formatCurrency(holding.unrealized_gain) ?? '—'}</div>
      </div>
    </li>
  )
}

/**
 * Top gainers/losers by the backend's own `unrealized_gain_percent` --
 * sorting and selection only, no new figure computed here (I2).
 * Contributors/detractors are strict sign-based buckets (never "top N
 * regardless of sign"), so a holding never appears in both.
 */
export function ContributorsDetractors({ holdings }: { holdings: HoldingWithMarketData[] }) {
  const contributors = topContributors(holdings)
  const detractors = topDetractors(holdings)

  if (contributors.length === 0 && detractors.length === 0) return null

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {contributors.length > 0 && (
        <div className="surface-card overflow-hidden">
          <div className="border-b border-[var(--color-border)] px-3 py-2">
            <span className="metric-label">Top contributors</span>
          </div>
          <ul className="divide-y divide-[var(--color-border)]">
            {contributors.map((h) => (
              <HoldingRow key={h.id} holding={h} tone="positive" />
            ))}
          </ul>
        </div>
      )}
      {detractors.length > 0 && (
        <div className="surface-card overflow-hidden">
          <div className="border-b border-[var(--color-border)] px-3 py-2">
            <span className="metric-label">Top detractors</span>
          </div>
          <ul className="divide-y divide-[var(--color-border)]">
            {detractors.map((h) => (
              <HoldingRow key={h.id} holding={h} tone="negative" />
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
