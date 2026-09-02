import { useState } from 'react'
import type { ReportWarning } from '../types/backend'
import { humanizeKey } from '../lib/format'

export function WarningsSection({ warnings }: { warnings: ReportWarning[] }) {
  const [open, setOpen] = useState(warnings.length <= 3)
  if (warnings.length === 0) return null

  return (
    <section
      aria-labelledby="warnings-heading"
      className="rounded-[var(--radius-md)] border border-[var(--color-status-medium)]/25 bg-[var(--color-status-medium)]/6 p-4 shadow-[var(--shadow-xs)]"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="warnings-list"
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <h2 id="warnings-heading" className="text-sm font-semibold text-[var(--color-status-medium)]">
          Data Quality &amp; Warnings ({warnings.length})
        </h2>
        <span
          aria-hidden="true"
          className={`text-[var(--color-text-faint)] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        >
          ▾
        </span>
      </button>
      {open && (
        <ul id="warnings-list" className="mt-3 space-y-2 text-sm">
          {warnings.map((warning, i) => (
            <li key={i} className="flex gap-2.5">
              <span className="mt-0.5 shrink-0 rounded-full bg-[var(--color-border)] px-2 py-0.5 text-xs font-medium text-[var(--color-text-muted)]">
                {humanizeKey(warning.source)}
              </span>
              <span className="text-[var(--color-text-muted)]">{warning.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
