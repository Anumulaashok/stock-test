import { HealthBadgeView } from '../layouts/SideNavHealthBadge'
import type { DataSourceStatus } from '../types/backend'

/**
 * Dev-only fixture gallery for the sidebar data-source health badge --
 * every phase/health combination rendered against fabricated `sources`,
 * with zero network calls. Registered only in dev (`main.tsx`, guarded
 * by `import.meta.env.DEV`) and lazy-loaded, so none of this reaches the
 * production bundle. A permanent asset, per the ML-panel fixture route
 * this one is modeled on.
 *
 * Each section is wrapped at a fixed 240px width (`SideNav`'s actual
 * column width) so expanded-list legibility can be judged at the real
 * size, not full-page width.
 */

function source(overrides: Partial<DataSourceStatus> = {}): DataSourceStatus {
  return {
    name: 'screener',
    label: 'Screener',
    type: 'historical/search',
    configured: true,
    status: 'SUCCESS',
    capabilities: ['company_search', 'daily_close_series'],
    primary_for: ['historical_price', 'company_search'],
    fallback_for: [],
    last_success_at: '2026-09-05T09:00:00+00:00',
    last_error_at: null,
    limitation: null,
    ...overrides,
  }
}

const ALL_HEALTHY: DataSourceStatus[] = [
  source(),
  source({ name: 'yfinance', label: 'yfinance', status: 'SUCCESS', primary_for: ['market_quote'] }),
  source({ name: 'indianapi', label: 'IndianAPI', status: 'SUCCESS', primary_for: ['financials'] }),
]

const DEGRADED_SERVING_LIMITATION: DataSourceStatus[] = [
  ...ALL_HEALTHY,
  source({
    name: 'fmp',
    label: 'FMP',
    status: 'SUCCESS',
    primary_for: [],
    fallback_for: ['market_quote'],
    limitation: 'Returns HTTP 402 for every NSE/BSE symbol on the current plan, so it is inert as a fallback for Indian tickers; US symbols are served normally.',
  }),
]

const DEGRADED_SERVING_FALLBACK: DataSourceStatus[] = [
  source({
    status: 'UNREACHABLE',
    primary_for: ['historical_price', 'company_search'],
    last_success_at: '2026-09-04T09:00:00+00:00',
    last_error_at: '2026-09-05T09:00:00+00:00',
  }),
  source({ name: 'yfinance', label: 'yfinance', status: 'SUCCESS', primary_for: [], fallback_for: ['historical_price'] }),
]

const ACTION_REQUIRED_ONE: DataSourceStatus[] = [
  source({ status: 'AUTH_EXPIRED', last_success_at: '2026-09-01T09:00:00+00:00' }),
  source({ name: 'yfinance', label: 'yfinance', status: 'SUCCESS', primary_for: ['market_quote'] }),
]

const ACTION_REQUIRED_MULTIPLE: DataSourceStatus[] = [
  source({ status: 'AUTH_EXPIRED', last_success_at: '2026-09-01T09:00:00+00:00' }),
  source({ name: 'indianapi', label: 'IndianAPI', status: 'INVALID', primary_for: ['financials'] }),
  source({ name: 'yfinance', label: 'yfinance', status: 'SUCCESS', primary_for: ['market_quote'] }),
]

const NONE_CONFIGURED: DataSourceStatus[] = [
  source({ configured: false, status: 'NOT_CONFIGURED', last_success_at: null }),
]

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2 border-b border-[var(--color-border)] pb-8 last:border-0">
      <div>
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--color-text-muted)]">{title}</h2>
        {note && <p className="support-text text-xs">{note}</p>}
      </div>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <div style={{ width: 240 }} className="border border-dashed border-[var(--color-border)] p-2">
          {children}
        </div>
      </div>
    </section>
  )
}

const noop = () => {}

export function HealthBadgeFixturePage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10">
      <div>
        <h1 className="text-lg font-bold">Data Source Health Badge Fixture Gallery (dev only)</h1>
        <p className="support-text text-xs">
          Every phase/health state rendered against fabricated data, no network calls. Boxed at 240px -- the actual
          sidebar column width -- to judge legibility at real size, not full-page width. Not reachable in production.
        </p>
      </div>

      <Section title="Loading (initial mount, before the first response)">
        <HealthBadgeView phase="loading" sources={null} reload={noop} />
      </Section>

      <Section title="Unknown -- the status endpoint itself failed" note="Never renders as healthy or as an alarm; own distinct neutral state.">
        <HealthBadgeView phase="error" sources={null} reload={noop} />
      </Section>

      <Section title="All healthy">
        <HealthBadgeView phase="ready" sources={ALL_HEALTHY} reload={noop} />
      </Section>

      <Section
        title="Degraded but serving -- documented limitation (FMP 402)"
        note="Must read as normal for Indian tickers, not an alarm -- neutral shape/color, not amber/red."
      >
        <HealthBadgeView phase="ready" sources={DEGRADED_SERVING_LIMITATION} reload={noop} />
      </Section>

      <Section title="Degraded but serving -- live fallback covering an unreachable primary">
        <HealthBadgeView phase="ready" sources={DEGRADED_SERVING_FALLBACK} reload={noop} />
      </Section>

      <Section title="Action required -- one source (AUTH_EXPIRED, with a fix link)">
        <HealthBadgeView phase="ready" sources={ACTION_REQUIRED_ONE} reload={noop} />
      </Section>

      <Section title="Action required -- multiple sources (AUTH_EXPIRED + INVALID)">
        <HealthBadgeView phase="ready" sources={ACTION_REQUIRED_MULTIPLE} reload={noop} />
      </Section>

      <Section title="No sources configured">
        <HealthBadgeView phase="ready" sources={NONE_CONFIGURED} reload={noop} />
      </Section>
    </main>
  )
}
