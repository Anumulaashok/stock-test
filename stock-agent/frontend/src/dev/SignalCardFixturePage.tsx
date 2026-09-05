import { SignalCard } from '../components/stock/SignalCard'
import { buildReport } from '../test/fixtures'

/**
 * Dev-only fixture gallery for the Wave 2 SignalCard (Overview tab),
 * no network calls. Registered only in dev (`main.tsx`, guarded by
 * `import.meta.env.DEV`) and lazy-loaded.
 */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2 border-b border-[var(--color-border)] pb-8 last:border-0">
      <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--color-text-muted)]">{title}</h2>
      {children}
    </section>
  )
}

export function SignalCardFixturePage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10">
      <div>
        <h1 className="text-lg font-bold">Signal Card Fixture Gallery (dev only)</h1>
        <p className="support-text text-xs">Populated, score-unavailable, and no-market states. Not reachable in production.</p>
      </div>

      <Section title="Populated -- good band, analyst ran, full coverage">
        <SignalCard report={buildReport()} />
      </Section>

      <Section title="Poor band">
        <SignalCard
          report={buildReport({
            summary: { overall_score: '22', overall_status: 'calculated', score_band: 'poor', signal: { label: 'weak', color: 'red', reason: 'Low score with high-severity risk.' }, investment_thesis: null, key_takeaways: [] },
          })}
        />
      </Section>

      <Section title="Score unavailable (never a fabricated 0)">
        <SignalCard
          report={buildReport({
            summary: { overall_score: null, overall_status: 'unavailable', score_band: null, signal: null, investment_thesis: null, key_takeaways: [] },
          })}
        />
      </Section>

      <Section title="No market section (no provenance line)">
        <SignalCard report={buildReport({ market: null })} />
      </Section>

      <Section title="Analyst did not run -- falls back to category reasons">
        <SignalCard
          report={buildReport({
            analyst: { source: 'analyst', available: false, investment_thesis: null, investment_thesis_evidence: null, strengths: [], weaknesses: [], category_analysis: [], key_takeaways: [], caveats: [] },
          })}
        />
      </Section>
    </main>
  )
}
