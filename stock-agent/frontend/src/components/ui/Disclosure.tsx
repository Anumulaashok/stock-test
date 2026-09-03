import type { ReactNode } from 'react'

/** Native `<details>`-backed expandable section -- keyboard accessible
 * for free, no JS state needed. Used for "expand for the real reason"
 * throughout the redesign (risk indicators, score components, fundamentals
 * beyond the highlighted few) so the default view stays uncluttered
 * without hiding the underlying evidence. */
export function Disclosure({
  summary,
  meta,
  children,
  defaultOpen = false,
}: {
  summary: ReactNode
  meta?: ReactNode
  children: ReactNode
  defaultOpen?: boolean
}) {
  return (
    <details className="group" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 py-1.5 text-sm">
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="text-[var(--color-text-faint)] transition-transform group-open:rotate-90">
            ▸
          </span>
          {summary}
        </span>
        {meta}
      </summary>
      <div className="mt-1 pl-4 text-sm text-[var(--color-text-muted)]">{children}</div>
    </details>
  )
}
