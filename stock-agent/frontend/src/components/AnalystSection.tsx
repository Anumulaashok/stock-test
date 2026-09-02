import { useState } from 'react'
import type { AnalystEvidence, ReportAnalystSection } from '../types/backend'
import { humanizeKey } from '../lib/format'

function EvidenceDisclosure({
  evidence,
  id,
  evidenceValues,
}: {
  evidence: AnalystEvidence
  id: string
  evidenceValues: Record<string, string>
}) {
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
        <div id={id} className="mt-1.5 rounded border border-[var(--color-border)] bg-[var(--color-accent-soft)] p-2">
          <p className="mb-1.5 text-[11px] text-[var(--color-text-faint)]">
            The deterministic analysis above supplied these figures to the AI — it did not calculate them itself:
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {entries.map(({ namespace, name }) => {
              const value = evidenceValues[name]
              return (
                <li
                  key={`${namespace}-${name}`}
                  className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-1.5 py-0.5 text-xs"
                  title={`${humanizeKey(namespace)} evidence`}
                >
                  <span>{humanizeKey(name)}</span>
                  {value && <span className="text-[var(--color-text-faint)]">: {value}</span>}
                </li>
              )
            })}
          </ul>
        </div>
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

export function AnalystSection({
  analyst,
  evidenceValues = {},
}: {
  analyst: ReportAnalystSection | null
  evidenceValues?: Record<string, string>
}) {
  if (!analyst || !analyst.available) {
    return (
      <section aria-labelledby="analyst-heading">
        <h2 id="analyst-heading" className="section-heading mb-3">
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
    <section aria-labelledby="analyst-heading" className="surface-card space-y-5 p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="analyst-heading" className="section-heading">
          AI Analyst
        </h2>
        <span className="text-xs text-[var(--color-text-faint)]">Explanatory commentary — not a recommendation</span>
      </div>

      {analyst.investment_thesis && (
        <div>
          <h3 className="text-sm font-semibold">Investment Thesis</h3>
          <p className="mt-1.5 text-sm leading-relaxed text-[var(--color-text-muted)]">{analyst.investment_thesis}</p>
          {analyst.investment_thesis_evidence && (
            <EvidenceDisclosure evidence={analyst.investment_thesis_evidence} id="thesis-evidence" evidenceValues={evidenceValues} />
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold">Strengths</h3>
          <BulletList items={analyst.strengths} />
        </div>
        <div>
          <h3 className="text-sm font-semibold">Weaknesses</h3>
          <BulletList items={analyst.weaknesses} />
        </div>
      </div>

      {analyst.category_analysis.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">Category Analysis</h3>
          <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {analyst.category_analysis.map((category) => (
              <div key={category.category} className="surface-card surface-card--interactive p-3.5">
                <h4 className="text-sm font-semibold">{humanizeKey(category.category)}</h4>
                <p className="mt-1 text-sm text-[var(--color-text-muted)]">{category.text}</p>
                <EvidenceDisclosure evidence={category.evidence} id={`evidence-${category.category}`} evidenceValues={evidenceValues} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <h3 className="text-sm font-semibold">Key Takeaways</h3>
        <BulletList items={analyst.key_takeaways} />
      </div>

      <div>
        <h3 className="text-sm font-semibold">Caveats</h3>
        <BulletList items={analyst.caveats} />
      </div>
    </section>
  )
}
