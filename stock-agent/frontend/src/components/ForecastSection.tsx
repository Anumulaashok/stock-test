import type { ReportForecastMetric, ReportForecastSection, ReportValuationScenario } from '../types/backend'
import { humanizeKey } from '../lib/format'
import { MetricStatusBadge } from './StatusBadge'

const SCENARIO_LABEL: Record<string, string> = {
  bear: 'Bear',
  base: 'Base',
  bull: 'Bull',
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

  if (!hasFinancials && !hasScenarios && !hasPriceTrend) {
    return null
  }

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

      {hasPriceTrend && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
            Price Trend Extrapolation
          </h3>
          <div className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {forecast.price_trend.map((point) => (
                <span key={point.day_offset} className="font-mono-nums">
                  +{point.day_offset}d: {point.formatted_projected_price ?? 'unavailable'}
                </span>
              ))}
            </div>
            {forecast.price_trend_disclaimer && (
              <p className="mt-2 border-t border-[var(--color-border)] pt-2 text-xs text-[var(--color-text-faint)]">
                {forecast.price_trend_disclaimer}
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
