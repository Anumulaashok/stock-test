import { useEffect, useState } from 'react'
import { fetchMarketOpportunity } from '../api/sectors'
import { ApiError } from '../api/client'
import { toDisplayNumber } from '../lib/format'
import type { MarketOpportunityResult, SectorSummary } from '../types/backend'

const OUTLOOK_CLASS: Record<SectorSummary['outlook'], string> = {
  bullish: 'text-[var(--color-status-positive)] bg-[var(--color-status-positive)]/10 border-[var(--color-status-positive)]/30',
  neutral: 'text-[var(--color-status-info)] bg-[var(--color-status-info)]/10 border-[var(--color-status-info)]/30',
  bearish: 'text-[var(--color-status-negative)] bg-[var(--color-status-negative)]/10 border-[var(--color-status-negative)]/30',
}

const RISK_CLASS: Record<SectorSummary['risk'], string> = {
  low: 'text-[var(--color-status-positive)]',
  medium: 'text-[var(--color-status-medium)]',
  high: 'text-[var(--color-status-negative)]',
}

function score(value: string | null): string {
  const formatted = toDisplayNumber(value, 0)
  return formatted === null ? '—' : formatted
}

function SectorCard({ sector, rank, onPickStock }: { sector: SectorSummary; rank: number; onPickStock: (ticker: string) => void }) {
  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-soft)] text-xs font-semibold text-[var(--color-accent)]">
            {rank}
          </span>
          <h3 className="text-sm font-semibold">{sector.sector}</h3>
        </div>
        <span
          className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${OUTLOOK_CLASS[sector.outlook]}`}
        >
          {sector.outlook}
        </span>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-semibold tabular-nums">{score(sector.sector_score)}</span>
        <span className="text-xs text-[var(--color-text-faint)]">/ 100</span>
        <span className={`ml-auto text-xs font-medium capitalize ${RISK_CLASS[sector.risk]}`}>{sector.risk} risk</span>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-[var(--color-text-faint)]">
        <dt>Growth</dt>
        <dd className="text-right tabular-nums text-[var(--color-text-muted)]">{score(sector.growth_score)}</dd>
        <dt>Valuation</dt>
        <dd className="text-right tabular-nums text-[var(--color-text-muted)]">{score(sector.valuation_score)}</dd>
        {sector.news_headline_count > 0 && (
          <>
            <dt>Recent headlines</dt>
            <dd className="text-right tabular-nums text-[var(--color-text-muted)]">{sector.news_headline_count}</dd>
          </>
        )}
      </dl>

      {sector.top_stocks.length > 0 && (
        <ul className="flex flex-col gap-1 border-t border-[var(--color-border)] pt-2">
          {sector.top_stocks.map((stock) => (
            <li key={stock.ticker}>
              <button
                type="button"
                onClick={() => onPickStock(stock.ticker)}
                className="flex w-full items-center justify-between rounded px-1 py-0.5 text-left text-xs hover:bg-[var(--color-accent-soft)]"
              >
                <span className="font-medium">{stock.ticker}</span>
                <span className="tabular-nums text-[var(--color-text-faint)]">{score(stock.overall_score)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className="text-[11px] text-[var(--color-text-faint)]">
        {sector.constituents_evaluated}/{sector.constituents_total} constituents scored
      </p>
    </div>
  )
}

/**
 * "Market Opportunity" -- sector ranking built entirely from the app's
 * own deterministic per-ticker scoring (see app/sectors/service.py).
 * Clicking a constituent ticker hands off to the normal research flow
 * for that ticker (`onSelectTicker`), same as the watchlist/search.
 */
export function SectorOverview({ onSelectTicker }: { onSelectTicker: (ticker: string) => void }) {
  const [data, setData] = useState<MarketOpportunityResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  async function load(forceRefresh: boolean) {
    try {
      const result = await fetchMarketOpportunity(forceRefresh)
      setData(result)
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load sector rankings.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    load(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <section aria-labelledby="market-opportunity-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 id="market-opportunity-heading" className="section-heading">
            Market Opportunity
          </h2>
          <p className="text-xs text-[var(--color-text-faint)]">
            Sectors ranked by average deterministic score across a curated set of constituent stocks.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setRefreshing(true)
            load(true)
          }}
          disabled={loading || refreshing}
          className="btn-secondary shrink-0 px-3 py-1.5 text-xs"
        >
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {loading && <p className="text-sm text-[var(--color-text-faint)]">Loading sector rankings…</p>}
      {error && <p className="text-sm text-[var(--color-status-critical)]">{error}</p>}
      {data && data.status === 'unavailable' && !error && (
        <p className="text-sm text-[var(--color-text-faint)]">
          Sector ranking is unavailable — configure a financial data provider to enable it.
        </p>
      )}

      {data && data.sectors.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.sectors.map((sector, i) => (
            <SectorCard key={sector.sector} sector={sector} rank={i + 1} onPickStock={onSelectTicker} />
          ))}
        </div>
      )}
    </section>
  )
}
