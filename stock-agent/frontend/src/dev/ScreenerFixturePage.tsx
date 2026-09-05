import { ScreenerView } from '../routes/ScreenerPage'
import type { RecentResearchEntry } from '../types/backend'

/**
 * Dev-only fixture for the Screener, rendering the real `ScreenerView`
 * (the same component the real page uses once fetched) directly
 * against fabricated entries -- zero network calls. Registered only in
 * dev (`main.tsx`, guarded by `import.meta.env.DEV`) and lazy-loaded.
 */

function entry(overrides: Partial<RecentResearchEntry> = {}): RecentResearchEntry {
  return {
    ticker: 'ACME', company_name: 'Acme Corp', research_run_id: 'r1', research_date: '2026-08-01',
    status: 'COMPLETED', run_type: 'NORMAL', overall_score: '78', band: 'good', completed_at: '2026-08-01T00:00:00+00:00',
    ...overrides,
  }
}

const FIXTURE_ENTRIES: RecentResearchEntry[] = [
  entry({ ticker: 'ACME', overall_score: '92', band: 'excellent' }),
  entry({ ticker: 'BETA', company_name: 'Beta Ltd', overall_score: '78', band: 'good', completed_at: '2026-08-03T00:00:00+00:00' }),
  entry({ ticker: 'GAMMA', company_name: 'Gamma Inc', overall_score: '55', band: 'fair', completed_at: '2026-07-20T00:00:00+00:00' }),
  entry({ ticker: 'DELTA', company_name: 'Delta Co', overall_score: '30', band: 'poor', completed_at: '2026-07-15T00:00:00+00:00' }),
  entry({ ticker: 'EPSILON', company_name: null, overall_score: null, band: null, completed_at: null, status: 'PARTIAL' }),
]

export function ScreenerFixturePage() {
  return <ScreenerView entries={FIXTURE_ENTRIES} />
}
