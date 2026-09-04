import { EmptyState } from '../SectionHeader'
import { formatDate, humanizeKey, isSafeHttpUrl } from '../../lib/format'
import type { NewsImpactEventSummary, NewsImpactSection, RecentNewsItem } from '../../types/mlForecast'

function pct(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(decimals)}%`
}

function pctSigned(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(decimals)}%`
}

/** Plain, uncolored badge -- deliberately never green/red. Sentiment,
 * event type and market timing are all classification fields (computed
 * labels), not calls, and I4 forbids letting a badge's color read as a
 * buy/sell signal the way it would elsewhere in the app. */
function Tag({ children }: { children: string }) {
  return (
    <span className="rounded border border-[var(--color-border)] px-1.5 py-0.5 text-xs text-[var(--color-text-muted)]">
      {children}
    </span>
  )
}

function RecentEventRow({ item }: { item: RecentNewsItem }) {
  return (
    <li className="flex flex-col gap-1 border-b border-[var(--color-border)] pb-2 last:border-0 last:pb-0">
      <div>
        {isSafeHttpUrl(item.url) ? (
          <a href={item.url} target="_blank" rel="noreferrer" className="hover:underline">
            {item.headline}
          </a>
        ) : (
          item.headline
        )}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <Tag>{humanizeKey(item.event_type)}</Tag>
        <Tag>{`${humanizeKey(item.sentiment)} sentiment`}</Tag>
        <Tag>{humanizeKey(item.market_timing)}</Tag>
        <span className="support-text text-xs">{formatDate(item.published_at)}</span>
      </div>
    </li>
  )
}

/** "How this event type has resolved before" -- a backward-looking
 * statistic, never attached to any specific headline above as its
 * expected move. That attachment is exactly what makes a number like
 * this misleading instead of informative; keeping it in its own list,
 * scoped to an event TYPE rather than an event, is the guardrail. */
function EventStudyRow({ stat }: { stat: NewsImpactEventSummary }) {
  return (
    <li className={`flex flex-col gap-1 border-b border-[var(--color-border)] pb-2 last:border-0 last:pb-0 ${stat.is_reliable ? '' : 'opacity-60'}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{humanizeKey(stat.event_type)}</span>
        <span className="support-text text-xs">n={stat.sample_size}</span>
      </div>
      {!stat.is_reliable && (
        <p className="support-text text-xs">Flagged unreliable by the backend -- small or noisy sample.</p>
      )}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div className="support-text">5-session median (past occurrences)</div>
          <div>{pctSigned(stat.median_return_5d)} · {pct(stat.positive_rate_5d)} positive</div>
        </div>
        <div>
          <div className="support-text">14-session median (past occurrences)</div>
          <div>{pctSigned(stat.median_return_14d)} · {pct(stat.positive_rate_14d)} positive</div>
        </div>
      </div>
    </li>
  )
}

/** `NewsImpactSection` from `MlForecastResult` (already fetched by the
 * caller -- no separate `/news-impact` request needed, that endpoint
 * returns this exact shape). `recent_events` ("this happened") and
 * `historical_statistics` ("how this event type resolved before, n=N")
 * are different epistemic objects and stay in separate, separately
 * labeled sections rather than one undifferentiated list. */
export function NewsImpactPanel({ newsImpact }: { newsImpact: NewsImpactSection }) {
  if (!newsImpact.data_available) {
    return (
      <div className="flex flex-col gap-2">
        <h4 className="text-sm font-semibold">News Impact</h4>
        <EmptyState title="News-derived signals unavailable" reason={newsImpact.note ?? undefined} />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <h4 className="text-sm font-semibold">News Impact</h4>

      <div>
        <div className="mb-1.5 support-text text-xs uppercase tracking-wide">Recent events</div>
        {newsImpact.recent_events.length === 0 ? (
          <EmptyState title="No recent classified events" />
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {newsImpact.recent_events.map((item) => (
              <RecentEventRow key={`${item.headline}-${item.published_at}`} item={item} />
            ))}
          </ul>
        )}
      </div>

      <div>
        <div className="mb-1.5 support-text text-xs uppercase tracking-wide">
          Past reaction by event type -- not a projection
        </div>
        {newsImpact.historical_statistics.length === 0 ? (
          <EmptyState title="No event-type history yet" reason="Builds up as more classified events accumulate for this ticker." />
        ) : (
          <ul className="flex flex-col gap-2">
            {newsImpact.historical_statistics.map((stat) => (
              <EventStudyRow key={stat.event_type} stat={stat} />
            ))}
          </ul>
        )}
      </div>

      {newsImpact.note && <p className="support-text text-xs">{newsImpact.note}</p>}
    </div>
  )
}
