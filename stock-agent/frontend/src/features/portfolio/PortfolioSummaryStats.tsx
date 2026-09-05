import { formatCompactINR, formatSignedPercent } from '../../lib/format'
import type { PortfolioSummary } from '../../types/backend'
import { toneClass, toneFor } from './toneFor'

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'positive' | 'negative' }) {
  return (
    <div>
      <div className="metric-label">{label}</div>
      <div className={`font-mono-nums ${toneClass(tone)}`} style={{ fontSize: 'var(--text-metric-value)', fontWeight: 700 }}>
        {value}
      </div>
    </div>
  )
}

/** The four headline portfolio numbers the backend actually gives us --
 * no sector/allocation/today's-P&L breakdown, since `PortfolioSummary`
 * carries none of that data (see `types/backend.ts`). */
export function PortfolioSummaryStats({ summary }: { summary: PortfolioSummary }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="surface-card grid grid-cols-2 gap-4 p-4 sm:grid-cols-4">
        <Stat label="Invested" value={formatCompactINR(summary.invested_capital) ?? '—'} />
        <Stat label="Value" value={formatCompactINR(summary.portfolio_value) ?? '—'} />
        <Stat
          label="Gain / Loss"
          value={formatCompactINR(summary.unrealized_gain) ?? '—'}
          tone={toneFor(summary.unrealized_gain)}
        />
        <Stat
          label="Gain / Loss %"
          value={formatSignedPercent(summary.unrealized_gain_percent) ?? '—'}
          tone={toneFor(summary.unrealized_gain_percent)}
        />
      </div>

      {summary.warnings.length > 0 && (
        <ul className="list-inside list-disc support-text">
          {summary.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
