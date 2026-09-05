import { CrossoverBadge } from '../SignalBadge'
import { PriceChart, type ForecastLineChartReferenceLine, type PriceChartVolumePoint } from '../PriceChart'
import { allHistoricalPrices } from '../ForecastSection'
import type { ReportForecastSection } from '../../types/backend'

function toNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/** Daily volume, chronologically -- reshapes `historical_prices.volume`
 * the same way `allHistoricalPrices` reshapes `.close`. Exported for
 * unit testing. */
export function historicalVolume(forecast: ReportForecastSection): PriceChartVolumePoint[] {
  return forecast.historical_prices
    .map((p) => ({ date: p.date, value: toNumber(p.volume) }))
    .filter((p): p is PriceChartVolumePoint => p.value !== null)
    .sort((a, b) => a.date.localeCompare(b.date))
}

const SMA_COLOR = ['#8a6d00', '#7a3ab3']

/** The current 50/200-day SMA as flat reference lines -- NOT a moving
 * average traced across history. `historical_prices`/`daily_price_
 * history` carries a per-day DMA50/DMA200 series in the DB (Screener
 * import), but that series is never threaded through to
 * `report.forecast` (see BACKLOG.md) -- so this shows the one real,
 * backend-computed number that IS on the report: today's SMA value,
 * exactly as `ForecastSection`'s own indicator toggle already does.
 * Exported for unit testing. */
export function currentSmaReferenceLines(forecast: ReportForecastSection): ForecastLineChartReferenceLine[] {
  return forecast.moving_averages
    .map((ma, i) => {
      const value = toNumber(ma.value)
      return value === null ? null : { label: `Current ${ma.window}-day SMA`, value, color: SMA_COLOR[i % SMA_COLOR.length] }
    })
    .filter((r): r is ForecastLineChartReferenceLine => r !== null)
}

/**
 * Shared price chart for the Technical and Overview tabs -- close price
 * + volume sub-chart + the current SMA50/SMA200 level + the crossover
 * badge, all read directly from `report.forecast` (no new fetch, no
 * client-side DMA/crossover computation). Two real callers from the
 * start (TechnicalSection, OverviewTab), per G6.
 */
export function PriceChartSection({ forecast }: { forecast: ReportForecastSection | null }) {
  if (!forecast || !forecast.available) return null

  const historical = allHistoricalPrices(forecast.historical_prices)
  if (historical.length === 0) {
    return (
      <div className="flex flex-col items-center gap-1.5 py-10 text-center">
        <p className="text-xs text-[var(--color-text-faint)]">No price history to chart.</p>
        <p className="text-xs text-[var(--color-text-faint)]">
          Import this ticker's price history in{' '}
          <a href="/settings/system" className="font-medium text-[var(--color-accent-strong)] hover:underline">
            Settings → System → Import Historical Data
          </a>{' '}
          to unlock this.
        </p>
      </div>
    )
  }

  const volume = historicalVolume(forecast)
  const referenceLines = currentSmaReferenceLines(forecast)

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <h3 className="card-heading">Price</h3>
        <CrossoverBadge crossover={forecast.crossover} />
      </div>
      <PriceChart historical={historical} predicted={[]} referenceLines={referenceLines} volume={volume} ariaLabel="Price chart" />
      {referenceLines.length > 0 && (
        <p className="support-text text-xs">
          SMA lines show today's 50/200-day average level, not a moving trace across history.
        </p>
      )}
    </div>
  )
}
