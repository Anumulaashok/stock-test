import type { ReportForecastMetric, ReportForecastSection, ReportValuationScenario } from '../types/backend'
import { humanizeKey } from '../lib/format'
import { MetricStatusBadge } from './StatusBadge'
import { ForecastLineChart, type ForecastLineChartMarker, type ForecastLineChartReferenceLine } from './ForecastLineChart'
import { TechnicalSignalBadge } from './SignalBadge'

const SCENARIO_LABEL: Record<string, string> = {
  bear: 'Bear',
  base: 'Base',
  bull: 'Bull',
}

const CROSSOVER_LABEL: Record<string, string> = {
  golden_cross: 'Golden cross (bullish)',
  death_cross: 'Death cross (bearish)',
  neutral: 'Neutral',
}

const METHOD_COLORS = ['#2952a3', '#b5540a', '#3a6b35', '#8a6d00', '#7a3ab3']

function toNumber(value: string | null): number | null {
  if (value === null) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function ForecastMetricCard({ metric }: { metric: ReportForecastMetric }) {
  return (
    <div className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-[var(--color-text-muted)]">{humanizeKey(metric.name)}</span>
        {metric.status !== 'calculated' && <MetricStatusBadge status={metric.status} />}
      </div>
      {metric.status === 'calculated' ? (
        <>
          <div className="mt-1 text-xs text-[var(--color-text-faint)]">
            Historical CAGR: <span className="font-mono-nums">{metric.formatted_historical_cagr}</span>
          </div>
          <dl className="mt-2 space-y-0.5 border-t border-[var(--color-border)] pt-2 text-xs">
            {metric.projections.map((year) => (
              <div key={year.year_offset} className="flex justify-between gap-2">
                <dt className="text-[var(--color-text-faint)]">Year +{year.year_offset}</dt>
                <dd className="font-mono-nums">{year.formatted_value ?? 'unavailable'}</dd>
              </div>
            ))}
          </dl>
        </>
      ) : (
        <p className="mt-1 text-xs text-[var(--color-text-faint)]">{metric.reason}</p>
      )}
    </div>
  )
}

function ValuationScenarioRow({ scenario }: { scenario: ReportValuationScenario }) {
  return (
    <div className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-[var(--color-text-muted)]">
          {SCENARIO_LABEL[scenario.scenario] ?? humanizeKey(scenario.scenario)}
        </span>
        {scenario.status !== 'calculated' && <MetricStatusBadge status={scenario.status} />}
      </div>
      <div className="mt-1 font-mono-nums text-xl font-semibold">
        {scenario.formatted_value_per_share ?? (
          <span className="text-base font-normal text-[var(--color-text-faint)]">Unavailable</span>
        )}
      </div>
      {scenario.fcf_growth_rate !== null && (
        <div className="text-xs text-[var(--color-text-faint)]">
          FCF growth assumption: <span className="font-mono-nums">{scenario.fcf_growth_rate}</span>
        </div>
      )}
      {scenario.reason && scenario.status !== 'calculated' && (
        <p className="mt-1 text-xs text-[var(--color-text-faint)]">{scenario.reason}</p>
      )}
    </div>
  )
}

export function ForecastSection({ forecast }: { forecast: ReportForecastSection | null }) {
  if (!forecast || !forecast.available) {
    return null
  }

  const hasFinancials = forecast.financial_metrics.length > 0
  const hasScenarios = forecast.valuation_scenarios.length > 0
  const hasPriceTrend = forecast.price_trend.length > 0
  const hasTechnical = forecast.moving_averages.length > 0 || forecast.technical_methods.length > 0

  if (!hasFinancials && !hasScenarios && !hasPriceTrend && !hasTechnical) {
    return null
  }

  const currentPrice = toNumber(forecast.current_price)
  const trendPoints = forecast.price_trend
    .map((point) => ({ day: point.day_offset, value: toNumber(point.projected_price) }))
    .filter((p): p is { day: number; value: number } => p.value !== null)
  const trendSeries =
    currentPrice !== null ? [{ day: 0, value: currentPrice }, ...trendPoints] : trendPoints

  const otherMethods = forecast.technical_methods.filter(
    (m) => m.method !== 'linear_regression' && m.status === 'calculated',
  )
  const methodMarkers: ForecastLineChartMarker[] = otherMethods
    .map((m, i) => {
      const value = toNumber(m.projected_price)
      return value === null
        ? null
        : { label: humanizeKey(m.method), day: m.projection_days, value, color: METHOD_COLORS[(i + 1) % METHOD_COLORS.length] }
    })
    .filter((m): m is ForecastLineChartMarker => m !== null)

  const referenceLines: ForecastLineChartReferenceLine[] = forecast.moving_averages
    .map((ma, i) => {
      const value = toNumber(ma.value)
      return value === null
        ? null
        : { label: `${ma.window}-day SMA`, value, color: i === 0 ? '#8a6d00' : '#7a3ab3' }
    })
    .filter((r): r is ForecastLineChartReferenceLine => r !== null)

  const hasChart = trendSeries.length > 0 || methodMarkers.length > 0

  return (
    <section aria-labelledby="forecast-heading">
      <h2
        id="forecast-heading"
        className="mb-1 text-sm font-semibold uppercase tracking-wide text-[var(--color-text-muted)]"
      >
        Forecast
      </h2>
      <p className="mb-3 text-xs text-[var(--color-text-faint)]">
        Deterministic extrapolation of historical data — not a recommendation, and never a single asserted price
        target.
      </p>

      {hasFinancials && (
        <div className="mb-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
            Financial Projections{forecast.projection_years ? ` (${forecast.projection_years}-year)` : ''}
          </h3>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {forecast.financial_metrics.map((metric) => (
              <ForecastMetricCard key={metric.name} metric={metric} />
            ))}
          </div>
        </div>
      )}

      {hasScenarios && (
        <div className="mb-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
            Valuation Scenarios (DCF)
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {forecast.valuation_scenarios.map((scenario) => (
              <ValuationScenarioRow key={scenario.scenario} scenario={scenario} />
            ))}
          </div>
        </div>
      )}

      {(hasPriceTrend || hasTechnical) && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
            Price Trend &amp; Technical Forecast
          </h3>
          <div className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
            {forecast.technical_signal && (
              <div className="mb-3 flex items-start justify-between gap-3">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
                  Technical Signal
                </h4>
                <TechnicalSignalBadge signal={forecast.technical_signal} />
              </div>
            )}

            {hasChart && (
              <>
                <ForecastLineChart
                  series={
                    trendSeries.length > 0
                      ? [{ label: 'Linear trend', color: '#2952a3', points: trendSeries }]
                      : []
                  }
                  markers={methodMarkers}
                  referenceLines={referenceLines}
                />
                <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-[var(--color-text-faint)]">
                  {trendSeries.length > 0 && (
                    <span className="flex items-center gap-1">
                      <span className="inline-block h-2 w-2 rounded-full" style={{ background: '#2952a3' }} /> Linear
                      trend
                    </span>
                  )}
                  {methodMarkers.map((m) => (
                    <span key={m.label} className="flex items-center gap-1">
                      <span className="inline-block h-2 w-2 rounded-full" style={{ background: m.color }} /> {m.label}
                    </span>
                  ))}
                  {referenceLines.map((r) => (
                    <span key={r.label} className="flex items-center gap-1">
                      <span className="inline-block h-2 w-0.5" style={{ background: r.color }} /> {r.label}
                    </span>
                  ))}
                </div>
              </>
            )}

            {hasPriceTrend && (
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-[var(--color-border)] pt-2 text-xs">
                {forecast.price_trend.map((point) => (
                  <span key={point.day_offset} className="font-mono-nums">
                    {point.date ?? `+${point.day_offset}d`}: {point.formatted_projected_price ?? 'unavailable'}
                  </span>
                ))}
              </div>
            )}
            {!hasPriceTrend && forecast.price_trend_status && (
              <p className="mt-2 text-xs text-[var(--color-text-faint)]">{forecast.price_trend_reason}</p>
            )}

            {forecast.crossover && (
              <p className="mt-2 border-t border-[var(--color-border)] pt-2 text-xs">
                Crossover signal ({forecast.crossover.short_window}d vs {forecast.crossover.long_window}d):{' '}
                {forecast.crossover.status === 'calculated' && forecast.crossover.signal ? (
                  <span className="font-medium">{CROSSOVER_LABEL[forecast.crossover.signal] ?? forecast.crossover.signal}</span>
                ) : (
                  <span className="text-[var(--color-text-faint)]">{forecast.crossover.reason ?? 'unavailable'}</span>
                )}
              </p>
            )}

            {forecast.technical_methods.length > 0 && (
              <dl className="mt-2 space-y-0.5 border-t border-[var(--color-border)] pt-2 text-xs">
                {forecast.technical_methods.map((method) => (
                  <div key={method.method} className="flex justify-between gap-2">
                    <dt className="text-[var(--color-text-faint)]">
                      {humanizeKey(method.method)}
                      {method.projected_date && (
                        <span className="ml-1 text-[var(--color-text-faint)]">(as of {method.projected_date})</span>
                      )}
                    </dt>
                    <dd className="font-mono-nums">
                      {method.status === 'calculated'
                        ? method.formatted_projected_price
                        : (method.reason ?? 'unavailable')}
                    </dd>
                  </div>
                ))}
              </dl>
            )}

            {(forecast.price_trend_disclaimer || forecast.technical_disclaimer) && (
              <p className="mt-2 border-t border-[var(--color-border)] pt-2 text-xs text-[var(--color-text-faint)]">
                {forecast.price_trend_disclaimer ?? forecast.technical_disclaimer}
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
