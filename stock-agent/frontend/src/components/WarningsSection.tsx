import { useState } from 'react'
import type { ReportWarning } from '../types/backend'
import { humanizeKey } from '../lib/format'

export function WarningsSection({ warnings }: { warnings: ReportWarning[] }) {
  const [open, setOpen] = useState(warnings.length <= 3)
  if (warnings.length === 0) return null

  return (
    <section
      aria-labelledby="warnings-heading"
      className="rounded border border-[var(--color-status-medium)]/30 bg-[var(--color-status-medium)]/5 p-3"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="warnings-list"
        className="flex w-full items-center justify-between text-left"
      >
        <h2 id="warnings-heading" className="text-sm font-semibold text-[var(--color-status-medium)]">
          Data Quality &amp; Warnings ({warnings.length})
        </h2>
        <span aria-hidden="true" className="text-xs text-[var(--color-text-faint)]">
          {open ? 'Hide' : 'Show'}
        </span>
      </button>
      {open && (
        <ul id="warnings-list" className="mt-2 space-y-1 text-sm">
          {warnings.map((warning, i) => (
            <li key={i} className="flex gap-2">
              <span className="shrink-0 rounded bg-[var(--color-border)] px-1.5 py-0.5 text-xs text-[var(--color-text-muted)]">
                {humanizeKey(warning.source)}
              </span>
              <span>{warning.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
