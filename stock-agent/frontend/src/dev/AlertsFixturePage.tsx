import { AlertsList } from '../features/alerts/AlertsList'
import { AddAlertForm } from '../features/alerts/AddAlertForm'
import type { Alert, AlertEvaluation } from '../types/alerts'

/**
 * Dev-only fixture gallery for the Wave 5 Alerts UI, no network calls.
 * Registered only in dev (`main.tsx`, guarded by `import.meta.env.DEV`)
 * and lazy-loaded.
 */

function alert(overrides: Partial<Alert> = {}): Alert {
  return {
    id: 'alert-1', ticker: 'ACME', condition_type: 'PRICE_ABOVE', threshold_value: '2500',
    is_active: true, created_at: '2026-08-01T00:00:00+00:00', updated_at: '2026-08-01T00:00:00+00:00',
    ...overrides,
  }
}

const noop = async () => {}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2 border-b border-[var(--color-border)] pb-8 last:border-0">
      <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--color-text-muted)]">{title}</h2>
      {children}
    </section>
  )
}

export function AlertsFixturePage() {
  const alerts: Alert[] = [
    alert({ id: 'a1', ticker: 'ACME', condition_type: 'PRICE_ABOVE', threshold_value: '2500' }),
    alert({ id: 'a2', ticker: 'BETA', condition_type: 'SCORE_BELOW', threshold_value: '40', is_active: false }),
    alert({ id: 'a3', ticker: 'GAMMA', condition_type: 'DMA_CROSSOVER_GOLDEN', threshold_value: null }),
    alert({ id: 'a4', ticker: 'DELTA', condition_type: 'REGIME_CHANGE', threshold_value: null }),
  ]

  const metEvaluation: AlertEvaluation = {
    alert_id: 'a1', ticker: 'ACME', condition_type: 'PRICE_ABOVE', status: 'met', observed_value: '2610.50', newly_triggered: true,
  }
  const notMetEvaluation: AlertEvaluation = {
    alert_id: 'a2', ticker: 'BETA', condition_type: 'SCORE_BELOW', status: 'not_met', observed_value: '62', newly_triggered: false,
  }
  const unavailableEvaluation: AlertEvaluation = {
    alert_id: 'a3', ticker: 'GAMMA', condition_type: 'DMA_CROSSOVER_GOLDEN', status: 'unavailable', observed_value: null, newly_triggered: false,
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10">
      <div>
        <h1 className="text-lg font-bold">Alerts Fixture Gallery (dev only)</h1>
        <p className="support-text text-xs">Every alert-row and evaluation state, no network calls. Not reachable in production.</p>
      </div>

      <Section title="Add alert form">
        <AddAlertForm onAdd={noop} />
      </Section>

      <Section title="All evaluation states -- met, not met, unavailable, and never-checked">
        <AlertsList
          alerts={alerts}
          evaluations={new Map([['a1', metEvaluation], ['a2', notMetEvaluation], ['a3', unavailableEvaluation]])}
          onToggleActive={noop}
          onDelete={noop}
        />
      </Section>

      <Section title="Empty state">
        <AlertsList alerts={[]} evaluations={new Map()} onToggleActive={noop} onDelete={noop} />
      </Section>
    </main>
  )
}
