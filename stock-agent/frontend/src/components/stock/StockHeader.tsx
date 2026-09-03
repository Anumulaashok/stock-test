import type { ReportCompany, ReportMarketSection } from '../../types/backend'
import { formatSignedPercent, formatDateTime } from '../../lib/format'
import { WatchlistButton } from '../WatchlistButton'

/** §3: name/ticker/exchange, price, day change, last updated, watchlist
 * -- and nothing else. Deliberately does not repeat the score/verdict
 * (that's `InvestmentVerdict`, immediately below it). Sticky so the
 * ticker and price stay visible while scrolling the rest of the page. */
export function StockHeader({
  company,
  market,
  authStatus,
  inWatchlist,
  watchlistPending,
  watchlistError,
  onToggleWatchlist,
}: {
  company: ReportCompany
  market: ReportMarketSection | null
  authStatus: 'checking' | 'authenticated' | 'anonymous'
  inWatchlist: boolean | null
  watchlistPending: boolean
  watchlistError: string | null
  onToggleWatchlist: () => void
}) {
  const changePercent = market?.change_percent !== null && market?.change_percent !== undefined ? Number(market.change_percent) : null
  const changeColor =
    changePercent === null
      ? 'text-[var(--color-text-faint)]'
      : changePercent >= 0
        ? 'text-[var(--color-status-positive)]'
        : 'text-[var(--color-status-negative)]'

  return (
    <header className="surface-card sticky top-3 z-10 flex flex-wrap items-center justify-between gap-4 p-4 backdrop-blur-md">
      <div className="min-w-0">
        <h1 className="truncate text-xl font-bold leading-tight tracking-tight">{company.name}</h1>
        <div className="mt-0.5 flex items-center gap-2 font-mono-nums text-xs text-[var(--color-text-faint)]">
          {company.ticker && <span>{company.ticker}</span>}
          {market?.source && <span>· {market.source}</span>}
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="text-right">
          {market?.formatted_current_price ? (
            <>
              <div className="metric-value">{market.formatted_current_price}</div>
              <div className={`font-mono-nums text-xs font-medium ${changeColor}`}>
                {formatSignedPercent(market.change_percent) ?? 'Unavailable'}
              </div>
            </>
          ) : (
            <div className="text-sm text-[var(--color-text-faint)]">Price unavailable</div>
          )}
          {market?.market_timestamp && (
            <div className="mt-0.5 text-[10px] text-[var(--color-text-faint)]">
              Updated {formatDateTime(market.market_timestamp)}
            </div>
          )}
        </div>
        <WatchlistButton
          status={authStatus}
          inWatchlist={inWatchlist}
          pending={watchlistPending}
          error={watchlistError}
          onToggle={onToggleWatchlist}
        />
      </div>
    </header>
  )
}
