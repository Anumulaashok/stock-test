import { SectionHeader, EmptyState } from '../SectionHeader'
import { MetricRow } from '../ui/MetricRow'
import { TechnicalSignalBadge } from '../SignalBadge'
import type { ReportForecastSection, ReportMarketSection } from '../../types/backend'

/**
 * Technical analysis, limited to what this backend actually computes:
 * price level, 52-week range, moving averages (DMA), the MA crossover,
 * and the deterministic technical-trend signal derived from them (see
 * `app/reporting/technical_signal.py`). There is no RSI, MACD,
 * Bollinger Bands, support/resistance, or volatility anywhere in this
 * codebase (verified by grep) -- do not add placeholders for them here.
 */
export function TechnicalSection({
  forecast,
  market,
}: {
  forecast: ReportForecastSection | null
  market: ReportMarketSection | null
}) {
  if (!forecast || !forecast.available) {
    return (
      <section aria-labelledby="technical-heading">
        <SectionHeader id="technical-heading" title="Technical" />
        <EmptyState title="Technical data unavailable" reason={forecast?.technical_disclaimer ?? undefined} />
      </section>
    )
  }

  return (
    <section aria-labelledby="technical-heading" className="flex flex-col gap-4">
      <SectionHeader
        id="technical-heading"
        title="Technical"
        action={<TechnicalSignalBadge signal={forecast.technical_signal} />}
      />

      <div className="surface-card p-4">
        <MetricRow label="Current price" value={forecast.formatted_current_price} />
        <MetricRow label="52-week high" value={market?.year_high ?? null} reason="Not reported by the source" />
        <MetricRow label="52-week low" value={market?.year_low ?? null} reason="Not reported by the source" />
      </div>

      {forecast.moving_averages.length > 0 && (
        <div className="surface-card p-4">
          <h3 className="card-heading mb-1">Moving averages</h3>
          {forecast.moving_averages.map((ma) => (
            <MetricRow
              key={ma.window}
              label={`${ma.window}-day DMA`}
              value={ma.formatted_value}
              reason={ma.reason}
            />
          ))}
          {forecast.crossover && (
            <MetricRow
              label={`${forecast.crossover.short_window}/${forecast.crossover.long_window}-day crossover`}
              value={forecast.crossover.signal}
              reason={forecast.crossover.reason}
            />
          )}
        </div>
      )}

      {forecast.technical_methods.length > 0 && (
        <div className="surface-card p-4">
          <h3 className="card-heading mb-1">Momentum projections</h3>
          {forecast.technical_methods.map((method) => (
            <MetricRow
              key={`${method.method}-${method.horizon}`}
              label={method.description}
              value={method.formatted_projected_price}
              reason={method.reason}
            />
          ))}
        </div>
      )}

      {forecast.technical_disclaimer && (
        <p className="support-text text-xs">{forecast.technical_disclaimer}</p>
      )}
    </section>
  )
}
