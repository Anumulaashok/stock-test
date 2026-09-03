import { formatDate, formatPercent, toDisplayNumber } from '../../lib/format'
import type { ForecastAccuracySummary } from '../../types/backend'

const INSUFFICIENT = 'insufficient backtest history'

function StatTile({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="support-text">{label}</dt>
      <dd className="font-mono-nums text-sm font-semibold" style={{ color: value ? 'var(--color-text)' : 'var(--color-text-faint)' }}>
        {value ?? INSUFFICIENT}
      </dd>
    </div>
  )
}

/** Renders `ForecastAccuracySummary` honestly -- every field comes
 * straight from the backend's realized-vs-predicted backtest; a null
 * field or a zero `evaluated_count` shows "insufficient backtest
 * history" text, never a fabricated number. */
export function ModelPerformancePanel({ summary }: { summary: ForecastAccuracySummary }) {
  const hasHistory = summary.evaluated_count > 0

  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <h3 className="card-heading">Forecast Accuracy — {summary.ticker}</h3>

      {!hasHistory ? (
        <p className="support-text">Accuracy unavailable — insufficient backtest history.</p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
            <StatTile label="Evaluated" value={String(summary.evaluated_count)} />
            <StatTile label="Newly evaluated" value={String(summary.newly_evaluated)} />
            <StatTile label="Mean abs. error" value={toDisplayNumber(summary.mean_absolute_error, 2)} />
            <StatTile label="Mean % error" value={formatPercent(summary.mean_percentage_error)} />
            <StatTile label="Direction accuracy" value={formatPercent(summary.direction_accuracy)} />
          </dl>

          {summary.entries.length > 0 && (
            <div className="-mx-4 overflow-x-auto">
              <table className="w-full min-w-[600px] text-left text-xs">
                <thead>
                  <tr className="text-[var(--color-text-faint)]">
                    <th className="px-4 py-1.5 font-medium">Horizon</th>
                    <th className="px-4 py-1.5 font-medium">Method</th>
                    <th className="px-4 py-1.5 font-medium">Predicted</th>
                    <th className="px-4 py-1.5 font-medium">Actual</th>
                    <th className="px-4 py-1.5 font-medium">% Error</th>
                    <th className="px-4 py-1.5 font-medium">Direction</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.entries.map((entry, i) => (
                    <tr key={`${entry.horizon}-${entry.method}-${entry.target_date}-${i}`} className="border-t border-[var(--color-border)]">
                      <td className="px-4 py-1.5">
                        {entry.horizon}
                        <span className="ml-1 text-[var(--color-text-faint)]">({formatDate(entry.target_date)})</span>
                      </td>
                      <td className="px-4 py-1.5">{entry.method}</td>
                      <td className="px-4 py-1.5 font-mono-nums">{toDisplayNumber(entry.predicted_price, 2) ?? '—'}</td>
                      <td className="px-4 py-1.5 font-mono-nums">{toDisplayNumber(entry.actual_price, 2) ?? '—'}</td>
                      <td className="px-4 py-1.5 font-mono-nums">{formatPercent(entry.percentage_error) ?? '—'}</td>
                      <td className="px-4 py-1.5">
                        {entry.direction_correct === null ? '—' : entry.direction_correct ? 'Correct' : 'Incorrect'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}

/** Entirely static and honest -- score-bucket outcome tracking has no
 * backend support yet (no recorded score-vs-realized-return history),
 * so this never renders a chart, table, or number for it. */
export function InvestmentScorePerformanceSection() {
  return (
    <div className="surface-card flex flex-col gap-2 p-4">
      <h3 className="card-heading">Investment Score Performance</h3>
      <p className="support-text">
        Score-bucket performance tracking (&gt;80, 60-80, &lt;60) requires historical outcome data not yet collected.
        Unavailable — insufficient backtest history.
      </p>
    </div>
  )
}
