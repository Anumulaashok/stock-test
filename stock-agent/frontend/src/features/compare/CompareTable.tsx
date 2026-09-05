import type { CompareRow } from './compareRows'

function Cell({ formattedValue, isBest, isWorst }: { formattedValue: string | null; isBest: boolean; isWorst: boolean }) {
  return (
    <td
      className={`px-3 py-2 font-mono-nums text-sm ${isBest ? 'font-semibold text-[var(--color-status-positive)]' : isWorst ? 'text-[var(--color-status-negative)]' : ''}`}
    >
      {formattedValue ?? <span className="text-xs text-[var(--color-text-faint)]">Unavailable</span>}
    </td>
  )
}

export function CompareTable({ title, rows, tickers }: { title: string; rows: CompareRow[]; tickers: string[] }) {
  if (rows.length === 0) return null
  return (
    <div className="surface-card overflow-x-auto">
      <table className="w-full min-w-[480px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-text-faint)]">
            <th className="px-3 py-2 font-semibold uppercase tracking-wide">{title}</th>
            {tickers.map((t) => (
              <th key={t} className="px-3 py-2 font-mono-nums font-semibold text-[var(--color-text-muted)]">
                {t}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--color-border)]">
          {rows.map((row) => (
            <tr key={row.label}>
              <td className="px-3 py-2 text-[var(--color-text-faint)]">{row.label}</td>
              {row.cells.map((cell) => (
                <Cell key={cell.ticker} {...cell} isBest={row.bestTicker === cell.ticker} isWorst={row.worstTicker === cell.ticker} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
