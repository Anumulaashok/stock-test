import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { useAsync } from '../../hooks/useAsync'
import { AsyncSection } from '../../components/ui/AsyncSection'
import { SkeletonRows } from '../../components/ui/Skeleton'
import { fetchPortfolioSummary } from '../../api/portfolio'
import { paths } from '../../routes/paths'
import { formatCompactINR, formatSignedPercent } from '../../lib/format'
import { toneClass, toneFor } from '../portfolio/toneFor'
import type { PortfolioSummary } from '../../types/backend'

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'positive' | 'negative' }) {
  return (
    <div>
      <div className="text-[9.5px] font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">{label}</div>
      <div className={`font-mono-nums text-base font-bold ${toneClass(tone)}`}>{value}</div>
    </div>
  )
}

/** Winners/losers is a plain count of already-server-computed
 * `unrealized_gain` signs, the same classification precedent as
 * `toneFor`/`changeTone` elsewhere -- not a new derived financial
 * figure. Holdings with an unavailable gain (no live price) count
 * toward neither bucket rather than being guessed. */
function winnersAndLosers(summary: PortfolioSummary): { winners: number; losers: number } {
  let winners = 0
  let losers = 0
  for (const holding of summary.holdings) {
    const tone = toneFor(holding.unrealized_gain)
    if (tone === 'positive') winners += 1
    else if (tone === 'negative') losers += 1
  }
  return { winners, losers }
}

/** Real portfolio totals from `GET /api/v1/portfolio/summary` -- the
 * same numbers `PortfolioSummaryStats` shows on the Portfolio page,
 * condensed for the dashboard plus a winners/losers count that page
 * doesn't show. */
export function PortfolioSnapshot() {
  const { status } = useAuth()
  const state = useAsync(fetchPortfolioSummary, [], { enabled: status === 'authenticated' })

  return (
    <section className="surface-card flex flex-col gap-3 p-4" aria-labelledby="portfolio-snapshot-heading">
      <div className="flex items-center justify-between gap-2">
        <h2 id="portfolio-snapshot-heading" className="card-heading">
          Portfolio Snapshot
        </h2>
        <Link to={paths.portfolio()} className="text-xs font-medium text-[var(--color-accent-strong)] hover:underline">
          Open
        </Link>
      </div>

      {status === 'checking' && <SkeletonRows count={2} />}

      {status === 'anonymous' && (
        <p className="support-text">
          <Link to={paths.login()} className="font-medium text-[var(--color-accent-strong)] hover:underline">
            Sign in
          </Link>{' '}
          to see your portfolio.
        </p>
      )}

      {status === 'authenticated' && (
        <AsyncSection state={state} onRetry={state.reload} errorTitle="Could not load your portfolio">
          {(summary) => {
            if (summary.holdings.length === 0) {
              return <p className="support-text">No holdings yet. Add one from the Portfolio page.</p>
            }
            const { winners, losers } = winnersAndLosers(summary)
            return (
              <div className="grid grid-cols-2 gap-x-3 gap-y-4">
                <Stat label="Invested" value={formatCompactINR(summary.invested_capital) ?? '—'} />
                <Stat label="Current Value" value={formatCompactINR(summary.portfolio_value) ?? '—'} />
                <Stat
                  label="Total P&L"
                  value={
                    summary.unrealized_gain === null
                      ? '—'
                      : `${formatCompactINR(summary.unrealized_gain)} (${formatSignedPercent(summary.unrealized_gain_percent) ?? '—'})`
                  }
                  tone={toneFor(summary.unrealized_gain)}
                />
                <div className="flex gap-4">
                  <Stat label="Winners" value={String(winners)} tone={winners > 0 ? 'positive' : undefined} />
                  <Stat label="Losers" value={String(losers)} tone={losers > 0 ? 'negative' : undefined} />
                </div>
              </div>
            )
          }}
        </AsyncSection>
      )}
    </section>
  )
}
