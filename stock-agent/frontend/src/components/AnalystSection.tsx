import { useState } from 'react'
import type { AnalystEvidence, ReportAnalystSection } from '../types/backend'
import { humanizeKey } from '../lib/format'

function EvidenceDisclosure({ evidence, id }: { evidence: AnalystEvidence; id: string }) {
  const [open, setOpen] = useState(false)
  const entries = (['financial', 'valuation', 'risk', 'research'] as const).flatMap((namespace) =>
    evidence[namespace].map((name) => ({ namespace, name })),
  )
  if (entries.length === 0) return null

  return (
    <div className="mt-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={id}
        className="text-xs font-medium text-[var(--color-accent)] underline-offset-2 hover:underline"
      >
        {open ? 'Hide evidence' : 'Why does the AI say this?'}
      </button>
      {open && (
        <ul id={id} className="mt-1 flex flex-wrap gap-1.5">
          {entries.map(({ namespace, name }) => (
            <li
              key={`${namespace}-${name}`}
              className="rounded border border-[var(--color-border)] bg-[var(--color-accent-soft)] px-1.5 py-0.5 text-xs"
              title={`${humanizeKey(namespace)} evidence`}
            >
              {humanizeKey(name)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) return <p className="text-sm text-[var(--color-text-faint)]">None reported.</p>
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  )
}

export function AnalystSection({ analyst }: { analyst: ReportAnalystSection | null }) {
  if (!analyst || !analyst.available) {
    return (
      <section aria-labelledby="analyst-heading">
        <h2 id="analyst-heading" className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          AI Analyst
        </h2>
        <p className="text-sm text-[var(--color-text-faint)]">
          The AI analyst commentary is unavailable for this analysis. Deterministic financial data above is
          unaffected.
        </p>
      </section>
    )
  }

  return (
    <section aria-labelledby="analyst-heading" className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h2 id="analyst-heading" className="text-sm font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          AI Analyst
        </h2>
        <span className="text-xs text-[var(--color-text-faint)]">Explanatory commentary — not a recommendation</span>
      </div>

      {analyst.investment_thesis && (
        <div>
          <h3 className="text-sm font-medium">Investment Thesis</h3>
          <p className="mt-1 text-sm">{analyst.investment_thesis}</p>
          {analyst.investment_thesis_evidence && (
            <EvidenceDisclosure evidence={analyst.investment_thesis_evidence} id="thesis-evidence" />
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <h3 className="text-sm font-medium">Strengths</h3>
          <BulletList items={analyst.strengths} />
        </div>
        <div>
          <h3 className="text-sm font-medium">Weaknesses</h3>
          <BulletList items={analyst.weaknesses} />
        </div>
      </div>

      {analyst.category_analysis.length > 0 && (
        <div>
          <h3 className="text-sm font-medium">Category Analysis</h3>
          <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {analyst.category_analysis.map((category) => (
              <div key={category.category} className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                <h4 className="text-sm font-medium">{humanizeKey(category.category)}</h4>
                <p className="mt-1 text-sm text-[var(--color-text-muted)]">{category.text}</p>
                <EvidenceDisclosure evidence={category.evidence} id={`evidence-${category.category}`} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <h3 className="text-sm font-medium">Key Takeaways</h3>
        <BulletList items={analyst.key_takeaways} />
      </div>

      <div>
        <h3 className="text-sm font-medium">Caveats</h3>
        <BulletList items={analyst.caveats} />
      </div>
    </section>
  )
}
