import { useAsync } from '../../hooks/useAsync'
import { AsyncSection } from '../../components/ui/AsyncSection'
import { SkeletonRows } from '../../components/ui/Skeleton'
import { fetchIndexQuotes } from '../../api/marketHistory'
import { toDisplayNumber, formatSignedPercent } from '../../lib/format'
import type { IndexQuote } from '../../types/backend'

/** Real Nifty 50 / Sensex levels from `GET /api/v1/market/indices` --
 * no market-breadth (advance/decline) data exists yet, so this stays a
 * plain index strip rather than a fabricated "market mood" widget. */

function changeTone(quote: IndexQuote): 'positive' | 'negative' | 'neutral' {
  if (quote.change_percent === null) return 'neutral'
  const value = Number(quote.change_percent)
  if (Number.isNaN(value) || value === 0) return 'neutral'
  return value > 0 ? 'positive' : 'negative'
}

const TONE_CLASS: Record<ReturnType<typeof changeTone>, string> = {
  positive: 'text-[var(--color-status-positive)]',
  negative: 'text-[var(--color-status-negative)]',
  neutral: 'text-[var(--color-text-faint)]',
}

function IndexCard({ quote }: { quote: IndexQuote }) {
  if (quote.status !== 'available' || quote.current_price === null) {
    return (
      <div className="surface-card flex items-center justify-between gap-2 p-3">
        <div>
          <div className="text-xs font-semibold text-[var(--color-text-muted)]">{quote.name}</div>
          <div className="font-mono-nums text-sm text-[var(--color-text-faint)]">— . —</div>
        </div>
        <span
          className="badge bg-[var(--color-status-medium)]/15 text-[var(--color-status-medium)]"
          title={quote.warning ?? undefined}
        >
          Unavailable
        </span>
      </div>
    )
  }

  const tone = changeTone(quote)
  const changeText = formatSignedPercent(quote.change_percent, 2) ?? '—'

  return (
    <div className="surface-card flex items-center justify-between gap-2 p-3">
      <div>
        <div className="text-xs font-semibold text-[var(--color-text-muted)]">{quote.name}</div>
        <div className="font-mono-nums text-sm">{toDisplayNumber(quote.current_price, 2)}</div>
      </div>
      <div className="text-right">
        <span className={`font-mono-nums text-sm font-medium ${TONE_CLASS[tone]}`}>{changeText}</span>
        <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">
          {quote.freshness ?? quote.source}
        </div>
      </div>
    </div>
  )
}

export function MarketSnapshot() {
  const state = useAsync(fetchIndexQuotes, [])

  return (
    <section className="flex flex-col gap-3" aria-labelledby="market-snapshot-heading">
      <div>
        <h2 id="market-snapshot-heading" className="section-heading">
          Market Snapshot
        </h2>
        <p className="support-text">Live index levels from the configured market data provider.</p>
      </div>
      <AsyncSection
        state={state}
        onRetry={state.reload}
        errorTitle="Could not load market data"
        skeleton={<SkeletonRows count={4} />}
      >
        {(data) =>
          data.indices.length === 0 ? (
            <p className="support-text">No index data available.</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {data.indices.map((quote) => (
                <IndexCard key={quote.symbol} quote={quote} />
              ))}
            </div>
          )
        }
      </AsyncSection>
    </section>
  )
}
