import type { SectorSummary } from '../../types/backend'
import { scoreText, UNAVAILABLE } from './scoreDisplay'

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

/** One sector's ranking card -- selectable, drives which sector's stocks
 * `SectorStockTable` shows. Score fields render "Unavailable" rather than
 * a fabricated 0 when the backend couldn't calculate them. */
export function SectorCard({
  sector,
  rank,
  selected,
  onSelect,
}: {
  sector: SectorSummary
  rank: number
  selected: boolean
  onSelect: () => void
}) {
  const scoreKnown = sector.sector_score !== null

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`surface-card surface-card--interactive flex flex-col gap-3 p-4 text-left ${
        selected ? 'border-[var(--color-accent)]' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-soft)] text-xs font-semibold text-[var(--color-accent-strong)]">
            {rank}
          </span>
          <h3 className="card-heading truncate">{sector.sector}</h3>
        </div>
        <span
          className={`badge shrink-0 border ${OUTLOOK_CLASS[sector.outlook]}`}
        >
          {sector.outlook}
        </span>
      </div>

      <div className="flex items-baseline gap-2">
        {scoreKnown ? (
          <>
            <span className="metric-value text-2xl">{scoreText(sector.sector_score)}</span>
            <span className="text-xs text-[var(--color-text-faint)]">/ 100</span>
          </>
        ) : (
          <span className="text-sm font-medium text-[var(--color-text-faint)]">Score {UNAVAILABLE.toLowerCase()}</span>
        )}
        <span className={`ml-auto shrink-0 text-xs font-medium capitalize ${RISK_CLASS[sector.risk]}`}>
          {sector.risk} risk
        </span>
      </div>

      <dl className="grid grid-cols-3 gap-x-2 gap-y-1 text-xs text-[var(--color-text-faint)]">
        <div className="min-w-0">
          <dt className="truncate">Growth</dt>
          <dd className="font-mono-nums text-[var(--color-text-muted)]">{scoreText(sector.growth_score)}</dd>
        </div>
        <div className="min-w-0">
          <dt className="truncate">Valuation</dt>
          <dd className="font-mono-nums text-[var(--color-text-muted)]">{scoreText(sector.valuation_score)}</dd>
        </div>
        <div className="min-w-0">
          <dt className="truncate">Momentum</dt>
          <dd className="font-mono-nums text-[var(--color-text-muted)]">{scoreText(sector.momentum_score)}</dd>
        </div>
      </dl>

      <p className="text-[11px] text-[var(--color-text-faint)]">
        {sector.constituents_evaluated}/{sector.constituents_total} constituents scored
        {sector.news_headline_count > 0 ? ` · ${sector.news_headline_count} recent headlines` : ''}
      </p>
    </button>
  )
}
