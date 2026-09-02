import type { ReactNode } from 'react'

/**
 * The one place every analysis section's heading is rendered, so the
 * hierarchy (page title > section heading > card heading) stays
 * consistent across the terminal instead of each section re-declaring
 * its own `<h2>` markup and spacing.
 */
export function SectionHeader({
  id,
  title,
  subtitle,
  meta,
  action,
}: {
  id: string
  title: string
  subtitle?: string
  meta?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
      <div>
        <h2 id={id} className="section-heading">
          {title}
        </h2>
        {subtitle && <p className="mt-1 support-text">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        {meta}
        {action}
      </div>
    </div>
  )
}

/** Consistent "nothing to show" treatment for a section — always states
 * why (the backend's own reason when one exists), never a bare
 * "Unavailable" with no context. */
export function EmptyState({ title, reason }: { title: string; reason?: string | null }) {
  return (
    <div className="surface-card p-5 text-sm">
      <p className="font-medium text-[var(--color-text-muted)]">{title}</p>
      {reason && <p className="mt-1 support-text">{reason}</p>}
    </div>
  )
}
