import type { ReportValuationMethod, ReportValuationSection } from '../types/backend'
import { humanizeKey } from '../lib/format'
import { MetricStatusBadge } from './StatusBadge'

const METHOD_LABEL: Record<string, string> = {
  dcf: 'DCF',
  pe: 'P/E',
  ev_ebitda: 'EV / EBITDA',
  pfcf: 'P / FCF',
}

function upsideColor(percent: string | null): string {
  if (percent === null) return 'text-[var(--color-text-faint)]'
  const value = Number(percent)
  if (Number.isNaN(value)) return 'text-[var(--color-text-faint)]'
  return value >= 0 ? 'text-[var(--color-status-positive)]' : 'text-[var(--color-status-negative)]'
}

function ValuationMethodCard({ method }: { method: ReportValuationMethod }) {
  return (
    <div className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-[var(--color-text-muted)]">
          {METHOD_LABEL[method.method] ?? humanizeKey(method.method)}
        </span>
        {method.status !== 'calculated' && <MetricStatusBadge status={method.status} />}
      </div>
      <div className="mt-1 font-mono-nums text-xl font-semibold">
        {method.formatted_value_per_share ?? (
          <span className="text-base font-normal text-[var(--color-text-faint)]">Unavailable</span>
        )}
      </div>
      {method.formatted_upside_downside && (
        <div className={`font-mono-nums text-sm ${upsideColor(method.upside_downside_percent)}`}>
          {Number(method.upside_downside_percent) >= 0 ? '+' : ''}
          {method.formatted_upside_downside} vs. current price
        </div>
      )}
      {method.reason && method.status !== 'calculated' && (
        <p className="mt-1 text-xs text-[var(--color-text-faint)]">{method.reason}</p>
      )}
      {Object.keys(method.assumptions).length > 0 && (
        <dl className="mt-2 space-y-0.5 border-t border-[var(--color-border)] pt-2 text-xs text-[var(--color-text-faint)]">
          {Object.entries(method.assumptions).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-2">
              <dt>{humanizeKey(key)}</dt>
              <dd className="font-mono-nums">{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}

export function ValuationSection({ valuation }: { valuation: ReportValuationSection | null }) {
  if (!valuation) {
    return (
      <section aria-labelledby="valuation-heading">
        <h2 id="valuation-heading" className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          Valuation
        </h2>
        <p className="text-sm text-[var(--color-text-faint)]">Valuation is unavailable for this analysis.</p>
      </section>
    )
  }

  return (
    <section aria-labelledby="valuation-heading">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 id="valuation-heading" className="text-sm font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          Valuation
        </h2>
        {valuation.formatted_current_share_price && (
          <span className="text-sm text-[var(--color-text-muted)]">
            Current price: <span className="font-mono-nums font-medium">{valuation.formatted_current_share_price}</span>
          </span>
        )}
      </div>
      <p className="mb-2 text-xs text-[var(--color-text-faint)]">
        Each valuation method is shown independently — the backend does not blend or average them into a single
        figure.
      </p>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {valuation.methods.map((method) => (
          <ValuationMethodCard key={method.method} method={method} />
        ))}
      </div>
    </section>
  )
}
