import { Link } from 'react-router-dom'
import { useAsync } from '../../hooks/useAsync'
import { AsyncSection } from '../../components/ui/AsyncSection'
import { fetchMarketOpportunity } from '../../api/sectors'
import { paths } from '../../routes/paths'
import { toDisplayNumber } from '../../lib/format'
import { toneFromBand, TONE_CLASS } from '../../lib/signals'
import type { ScoreBand, SectorStockSummary, SectorSummary } from '../../types/backend'

/** Top sectors + their best-scoring constituents from `GET
 * /api/v1/sectors` -- the backend already ranks `sectors` and each
 * sector's `top_stocks` descending by score (`app/sectors/service.py`),
 * so this only ever slices, never re-sorts or invents a number. */

const TOP_SECTOR_COUNT = 3
const TOP_STOCKS_PER_SECTOR = 3

const OUTLOOK_DOT: Record<SectorSummary['outlook'], string> = {
  bullish: 'bg-[var(--color-status-positive)]',
  neutral: 'bg-[var(--color-status-info)]',
  bearish: 'bg-[var(--color-status-negative)]',
}

function score(value: string | null): string {
  return toDisplayNumber(value, 0) ?? '—'
}

function StockChip({ stock }: { stock: SectorStockSummary }) {
  const tone = toneFromBand(stock.status === 'calculated' ? ((stock.band as ScoreBand | null) ?? null) : null)
  return (
    <Link
      to={paths.stock(stock.ticker)}
      className="surface-card surface-card--interactive flex flex-col gap-1 p-3"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-semibold">{stock.ticker}</span>
        <span className={`metric-value text-base ${TONE_CLASS[tone]}`}>
          {stock.status === 'calculated' ? score(stock.overall_score) : '—'}
        </span>
      </div>
      <span className="truncate text-[11px] text-[var(--color-text-faint)]">{stock.company_name}</span>
    </Link>
  )
}

function SectorGroup({ sector, rank }: { sector: SectorSummary; rank: number }) {
  const stocks = sector.top_stocks.slice(0, TOP_STOCKS_PER_SECTOR)
  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-soft)] text-[11px] font-bold text-[var(--color-accent-strong)]">
            {rank}
          </span>
          <span className="truncate text-[13px] font-semibold">{sector.sector}</span>
          <span className={`h-2 w-2 shrink-0 rounded-full ${OUTLOOK_DOT[sector.outlook]}`} title={sector.outlook} />
        </div>
        <span className="badge shrink-0 bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]">
          Score {score(sector.sector_score)}
        </span>
      </div>
      {stocks.length === 0 ? (
        <p className="support-text">No evaluated stocks in this sector yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {stocks.map((stock) => (
            <StockChip key={stock.ticker} stock={stock} />
          ))}
        </div>
      )}
    </div>
  )
}

/** Coarse, honestly-labeled risk callout -- derived only from
 * `SectorSummary.risk`, never a stock-level alert (no such data
 * exists). Omitted entirely when nothing is elevated. */
function ElevatedRiskSectors({ sectors }: { sectors: SectorSummary[] }) {
  const risky = sectors.filter((s) => s.risk === 'high')
  if (risky.length === 0) return null
  return (
    <p className="support-text">
      Elevated-risk sectors right now: {risky.map((s) => s.sector).join(', ')}.
    </p>
  )
}

export function TopOpportunities() {
  const state = useAsync(() => fetchMarketOpportunity(false), [])

  return (
    <section className="flex flex-col gap-4" aria-labelledby="top-opportunities-heading">
      <div>
        <h2 id="top-opportunities-heading" className="section-heading">
          Top Opportunities
        </h2>
        <p className="support-text">Sectors ranked by average deterministic score across curated constituents.</p>
      </div>
      <AsyncSection state={state} onRetry={state.reload} errorTitle="Could not load sector rankings">
        {(data) => {
          if (data.status === 'unavailable' || data.sectors.length === 0) {
            return <p className="support-text">Sector ranking is unavailable right now.</p>
          }
          const top = data.sectors.slice(0, TOP_SECTOR_COUNT)
          return (
            <>
              <div className="flex flex-col gap-3">
                {top.map((sector, i) => (
                  <SectorGroup key={sector.sector} sector={sector} rank={i + 1} />
                ))}
              </div>
              <ElevatedRiskSectors sectors={data.sectors} />
            </>
          )
        }}
      </AsyncSection>
    </section>
  )
}
