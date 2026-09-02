import type { InvestmentResearchReport, ReportRiskSection, ScoreBand } from '../types/backend'
import { toDisplayNumber, humanizeKey } from '../lib/format'
import { SignalBadge } from './SignalBadge'
import { WatchlistButton } from './WatchlistButton'

/**
 * The "what does the analysis currently say" summary at the top of the
 * page -- built entirely from fields the backend already computes
 * (`report.summary`, `report.scoring`, `report.risk`, `report.valuation`).
 * Never blends valuation methods into one "fair value" -- each
 * calculated method is shown separately, matching the backend's own
 * policy (see ValuationSection's own disclaimer).
 */

const BAND_COLOR: Record<string, string> = {
  excellent: 'var(--color-status-positive)',
  strong: 'var(--color-status-positive)',
  good: 'var(--color-status-low)',
  fair: 'var(--color-status-medium)',
  weak: 'var(--color-status-high)',
  poor: 'var(--color-status-critical)',
}

const CATEGORY_SUMMARY_ORDER = ['valuation', 'growth', 'profitability', 'financial_health'] as const

const METHOD_LABEL: Record<string, string> = {
  dcf: 'DCF',
  pe: 'P/E',
  ev_ebitda: 'EV / EBITDA',
  pfcf: 'P / FCF',
}

function riskSummary(risk: ReportRiskSection | null): { label: string; color: string } {
  if (!risk) return { label: 'Unavailable', color: 'var(--color-text-faint)' }
  if (risk.critical.length > 0) return { label: 'Critical', color: 'var(--color-status-critical)' }
  if (risk.high.length > 0) return { label: 'High', color: 'var(--color-status-high)' }
  if (risk.medium.length > 0) return { label: 'Moderate', color: 'var(--color-status-medium)' }
  if (risk.low.length > 0) return { label: 'Low', color: 'var(--color-status-low)' }
  return { label: 'None flagged', color: 'var(--color-status-positive)' }
}

function SummaryStat({
  label,
  value,
  band,
  color,
}: {
  label: string
  value: string
  band?: ScoreBand | null
  color?: string
}) {
  const resolvedColor = color ?? (band ? BAND_COLOR[band] : undefined)
  return (
    <div>
      <div className="metric-label">{label}</div>
      <div className="mt-1 font-mono-nums text-lg font-bold" style={resolvedColor ? { color: resolvedColor } : undefined}>
        {value}
      </div>
      {band && <div className="mt-0.5 text-xs capitalize text-[var(--color-text-faint)]">{band}</div>}
    </div>
  )
}

export function InvestmentSummary({
  report,
  authStatus,
  inWatchlist,
  watchlistPending,
  watchlistError,
  onToggleWatchlist,
}: {
  report: InvestmentResearchReport
  authStatus: 'checking' | 'authenticated' | 'anonymous'
  inWatchlist: boolean | null
  watchlistPending: boolean
  watchlistError: string | null
  onToggleWatchlist: () => void
}) {
  const score = toDisplayNumber(report.summary.overall_score)
  const risk = riskSummary(report.risk)
  const categoriesByKey = Object.fromEntries((report.scoring?.categories ?? []).map((c) => [c.category, c]))
  const calculatedMethods = (report.valuation?.methods ?? []).filter((m) => m.status === 'calculated')
  const usesAutoDerivedAssumptions = report.warnings.some((w) => /auto-derived|defaulted/i.test(w.message))

  return (
    <section aria-labelledby="investment-summary-heading" className="surface-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1
            id="investment-summary-heading"
            className="text-[length:var(--text-page-title)] font-bold leading-tight tracking-tight text-[var(--color-text)]"
          >
            {report.company.name}
          </h1>
          {report.company.ticker && (
            <p className="mt-1 font-mono-nums text-sm font-medium text-[var(--color-text-faint)]">
              {report.company.ticker}
            </p>
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

      <div className="mt-5 flex flex-wrap items-end justify-between gap-4">
        {report.valuation?.formatted_current_share_price ? (
          <div>
            <div className="metric-label">Current Price</div>
            <div className="metric-value">{report.valuation.formatted_current_share_price}</div>
          </div>
        ) : (
          <div>
            <div className="metric-label">Current Price</div>
            <div className="mt-1 text-sm text-[var(--color-text-faint)]">Unavailable</div>
          </div>
        )}
        <SignalBadge signal={report.summary.signal} />
      </div>

      <div className="mt-6 grid grid-cols-2 gap-x-4 gap-y-5 border-t border-[var(--color-border)] pt-5 sm:grid-cols-3 lg:grid-cols-5">
        <SummaryStat label="Score" value={score !== null ? `${score}/100` : 'Unavailable'} band={report.summary.score_band} />
        <SummaryStat label="Risk" value={risk.label} color={risk.color} />
        {CATEGORY_SUMMARY_ORDER.map((key) => {
          const category = categoriesByKey[key]
          if (!category) return null
          const value = toDisplayNumber(category.score)
          return (
            <SummaryStat
              key={key}
              label={humanizeKey(key)}
              value={value !== null ? value : 'Unavailable'}
              band={category.band}
            />
          )
        })}
      </div>

      {calculatedMethods.length > 0 && (
        <div className="mt-6 border-t border-[var(--color-border)] pt-5">
          <div className="metric-label mb-2">Valuation (each method shown independently, never blended)</div>
          <div className="flex flex-wrap gap-x-8 gap-y-3">
            {calculatedMethods.map((method) => {
              const upsideValue = method.upside_downside_percent !== null ? Number(method.upside_downside_percent) : null
              return (
                <div key={method.method}>
                  <div className="text-xs text-[var(--color-text-faint)]">
                    {METHOD_LABEL[method.method] ?? humanizeKey(method.method)} fair value
                  </div>
                  <div className="font-mono-nums text-base font-semibold">{method.formatted_value_per_share}</div>
                  {method.formatted_upside_downside && upsideValue !== null && (
                    <div
                      className={`font-mono-nums text-xs font-medium ${
                        upsideValue >= 0 ? 'text-[var(--color-status-positive)]' : 'text-[var(--color-status-negative)]'
                      }`}
                    >
                      {upsideValue >= 0 ? '+' : ''}
                      {method.formatted_upside_downside} vs. current price
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          {usesAutoDerivedAssumptions && (
            <p className="mt-2 text-xs text-[var(--color-text-faint)]">
              Uses auto-derived assumptions where none were supplied — see the Valuation section below for the full
              breakdown and reasoning.
            </p>
          )}
        </div>
      )}

      <p className="mt-5 border-t border-[var(--color-border)] pt-4 text-xs text-[var(--color-text-faint)]">
        Analysis generated {new Date(report.metadata.generated_at).toLocaleString()}
      </p>
    </section>
  )
}
