import { Link } from 'react-router-dom'
import type { SectorSummary } from '../../types/backend'
import { paths } from '../../routes/paths'
import { scoreText, UNAVAILABLE } from './scoreDisplay'

/** The selected sector's constituent stocks -- a real stock link
 * (`paths.stock`), never a raw ticker string, so it always navigates to
 * the same route the header search bar does. */
export function SectorStockTable({ sector }: { sector: SectorSummary }) {
  const stocks = sector.top_stocks

  return (
    <section className="surface-card flex flex-col gap-3 p-4" aria-label={`Top stocks in ${sector.sector}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="card-heading">Top stocks · {sector.sector}</h2>
          <p className="support-text">Best-scoring evaluated constituents in this sector.</p>
        </div>
        <span className="badge bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]">
          Sector score {scoreText(sector.sector_score)}
        </span>
      </div>

      {stocks.length === 0 && <p className="support-text">No constituents were evaluated for this sector.</p>}

      {stocks.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-[var(--color-text-faint)]">
              <tr>
                <th className="pb-2 pr-2">#</th>
                <th className="pb-2 pr-2">Stock</th>
                <th className="pb-2 pr-2">Score</th>
                <th className="pb-2">Band</th>
              </tr>
            </thead>
            <tbody>
              {stocks.map((stock, i) => {
                const calculated = stock.status === 'calculated'
                return (
                  <tr key={stock.ticker} className="border-t border-[var(--color-border)]">
                    <td className="py-2 pr-2 text-[var(--color-text-faint)]">{i + 1}</td>
                    <td className="py-2 pr-2">
                      <Link
                        to={paths.stock(stock.ticker)}
                        className="font-medium text-[var(--color-accent-strong)] hover:underline"
                      >
                        {stock.ticker}
                      </Link>
                      <div className="truncate text-[11px] text-[var(--color-text-faint)]">{stock.company_name}</div>
                    </td>
                    <td className="py-2 pr-2 font-mono-nums">{calculated ? scoreText(stock.overall_score) : UNAVAILABLE}</td>
                    <td className="py-2 capitalize text-[var(--color-text-muted)]">
                      {calculated && stock.band ? stock.band : UNAVAILABLE}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
