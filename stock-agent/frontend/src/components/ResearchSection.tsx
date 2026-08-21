import type { ReportResearchItem, ReportResearchSection } from '../types/backend'
import { formatDate, isSafeHttpUrl } from '../lib/format'
import { FreshnessBadge } from './StatusBadge'

function ResearchItemCard({ item }: { item: ReportResearchItem }) {
  const safeUrl = isSafeHttpUrl(item.url)
  return (
    <li className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-medium">{item.title}</h3>
        <FreshnessBadge freshness={item.freshness} />
      </div>
      {item.summary && <p className="mt-1 text-sm text-[var(--color-text-muted)]">{item.summary}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--color-text-faint)]">
        <span className="font-mono-nums">{item.id}</span>
        {item.publisher && <span>{item.publisher}</span>}
        {item.published_at && <span>{formatDate(item.published_at)}</span>}
        {safeUrl ? (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="text-[var(--color-accent)] underline underline-offset-2"
          >
            Source ↗
          </a>
        ) : (
          <span title="This link could not be verified as safe and was not made clickable.">
            Source unavailable
          </span>
        )}
      </div>
    </li>
  )
}

export function ResearchSection({ research }: { research: ReportResearchSection | null }) {
  if (!research || !research.available) {
    return (
      <section aria-labelledby="research-heading">
        <h2 id="research-heading" className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          Research
        </h2>
        <p className="text-sm text-[var(--color-text-faint)]">No research context is available for this analysis.</p>
      </section>
    )
  }

  return (
    <section aria-labelledby="research-heading">
      <h2 id="research-heading" className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
        Research
      </h2>
      {research.items.length === 0 ? (
        <p className="text-sm text-[var(--color-text-faint)]">No relevant research items were found.</p>
      ) : (
        <ul className="space-y-2">
          {research.items.map((item) => (
            <ResearchItemCard key={item.id} item={item} />
          ))}
        </ul>
      )}
    </section>
  )
}
