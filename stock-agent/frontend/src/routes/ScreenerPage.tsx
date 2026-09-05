import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchRecentResearch } from '../api/research'
import { useAsync } from '../hooks/useAsync'
import { AsyncSection } from '../components/ui/AsyncSection'
import { formatDate, toDisplayNumber } from '../lib/format'
import { toCsv, downloadCsv } from '../lib/csv'
import { paths } from './paths'
import {
  describeActiveFilters,
  filterEntries,
  filtersFromSearchParams,
  filtersToSearchParams,
  sortEntries,
  type ScreenerFilters,
  type ScreenerSort,
} from '../features/screener/screenerFilters'
import type { RecentResearchEntry, ScoreBand } from '../types/backend'

const RECENT_LIMIT = 100
const ALL_BANDS: ScoreBand[] = ['excellent', 'strong', 'good', 'fair', 'weak', 'poor']
const SORT_LABEL: Record<ScreenerSort, string> = {
  score_desc: 'Score (high to low)', score_asc: 'Score (low to high)', ticker_asc: 'Ticker (A-Z)', date_desc: 'Most recently researched',
}

function screenerToCsv(entries: RecentResearchEntry[]): string {
  return toCsv(
    ['ticker', 'company_name', 'overall_score', 'band', 'research_date', 'status'],
    entries.map((e) => [e.ticker, e.company_name, e.overall_score, e.band, e.research_date, e.status]),
  )
}

function FilterBar({ filters, onChange }: { filters: ScreenerFilters; onChange: (next: ScreenerFilters) => void }) {
  function toggleBand(band: ScoreBand) {
    const bands = filters.bands.includes(band) ? filters.bands.filter((b) => b !== band) : [...filters.bands, band]
    onChange({ ...filters, bands })
  }

  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <div>
        <div className="metric-label mb-1.5">Band</div>
        <div className="flex flex-wrap gap-1.5">
          {ALL_BANDS.map((band) => (
            <button
              key={band}
              type="button"
              onClick={() => toggleBand(band)}
              aria-pressed={filters.bands.includes(band)}
              className={`rounded-full border px-2.5 py-1 text-xs capitalize transition-colors ${
                filters.bands.includes(band)
                  ? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]'
                  : 'border-[var(--color-border)] text-[var(--color-text-muted)]'
              }`}
            >
              {band}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs">
          <span className="metric-label">Minimum score</span>
          <input
            type="number"
            min={0}
            max={100}
            value={filters.minScore ?? ''}
            onChange={(e) => onChange({ ...filters, minScore: e.target.value === '' ? null : Number(e.target.value) })}
            placeholder="e.g. 70"
            className="input-field w-28 px-3 py-1.5 font-mono-nums text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="metric-label">Sort by</span>
          <select
            value={filters.sort}
            onChange={(e) => onChange({ ...filters, sort: e.target.value as ScreenerSort })}
            className="input-field px-3 py-1.5 text-sm"
          >
            {Object.entries(SORT_LABEL).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  )
}

/**
 * Filters/sorts the up-to-100 most recently researched tickers this
 * app already tracks (`GET /recent`) -- reshaping only (band/score
 * bucketing, sorting by an already-known field), no new backend work.
 * Sector, sub-score, and computed-fundamental filters are not here:
 * `/recent` doesn't carry that data. See BACKLOG.md.
 */
export function ScreenerPage() {
  const state = useAsync(() => fetchRecentResearch(RECENT_LIMIT), [])

  return (
    <AsyncSection state={state} onRetry={state.reload} errorTitle="Could not load the screener">
      {(entries) => <ScreenerView entries={entries} />}
    </AsyncSection>
  )
}

/**
 * Exported for the dev-only fixture route (`src/dev/ScreenerFixturePage.tsx`)
 * -- renders directly against fabricated entries, zero network calls,
 * so filter/sort/CSV/empty-state behavior can be eyeballed without a
 * real fetch. Not used by any other production call site besides
 * `ScreenerPage` above.
 */
export function ScreenerView({ entries }: { entries: RecentResearchEntry[] }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = filtersFromSearchParams(searchParams)

  function setFilters(next: ScreenerFilters) {
    setSearchParams(filtersToSearchParams(next))
  }

  const filterDescription = describeActiveFilters(filters)
  const filtered = filterEntries(entries, filters)
  const sorted = sortEntries(filtered, filters.sort)

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-4 px-4 pb-32 pt-8">
      <div>
        <h1 className="text-xl font-semibold">Screener</h1>
        <p className="support-text">
          Filters the {RECENT_LIMIT} most recently researched tickers this app already tracks -- not the full listed
          universe.
        </p>
      </div>

      <FilterBar filters={filters} onChange={setFilters} />

      <ScreenerResults sorted={sorted} totalCount={entries.length} filterDescription={filterDescription} />
    </main>
  )
}

function ScreenerResults({
  sorted,
  totalCount,
  filterDescription,
}: {
  sorted: RecentResearchEntry[]
  totalCount: number
  filterDescription: string | null
}) {
  const rows = useMemo(() => sorted, [sorted])

  if (rows.length === 0) {
    return (
      <div className="surface-card flex flex-col items-center gap-1 p-8 text-center">
        <p className="card-heading">No results</p>
        <p className="support-text">
          {filterDescription ? `No tracked ticker matches: ${filterDescription}.` : 'No tickers have been researched yet.'}
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="support-text text-xs">
          {rows.length} of {totalCount} tracked
        </span>
        <button type="button" onClick={() => downloadCsv('screener', screenerToCsv(rows))} className="btn-secondary px-3 py-1.5 text-xs">
          Export CSV
        </button>
      </div>
      <div className="surface-card overflow-x-auto">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-text-faint)]">
              <th className="sticky left-0 bg-[var(--color-surface)] px-3 py-2 font-medium">Ticker</th>
              <th className="px-3 py-2 font-medium">Company</th>
              <th className="px-3 py-2 font-medium text-right">Score</th>
              <th className="px-3 py-2 font-medium">Band</th>
              <th className="px-3 py-2 font-medium">Researched</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {rows.map((entry) => (
              <tr key={entry.ticker} className="hover:bg-[var(--color-border)]/30">
                <td className="sticky left-0 bg-[var(--color-surface)] px-3 py-2 font-mono-nums font-semibold">
                  <Link to={paths.stock(entry.ticker)} className="text-[var(--color-accent-strong)] hover:underline">
                    {entry.ticker}
                  </Link>
                </td>
                <td className="px-3 py-2 text-[var(--color-text-muted)]">{entry.company_name ?? '—'}</td>
                <td className="px-3 py-2 text-right font-mono-nums">
                  {entry.overall_score !== null ? toDisplayNumber(entry.overall_score, 0) : <span className="text-xs text-[var(--color-text-faint)]">Not scored</span>}
                </td>
                <td className="px-3 py-2 capitalize text-[var(--color-text-muted)]">{entry.band ?? '—'}</td>
                <td className="px-3 py-2 font-mono-nums text-[var(--color-text-faint)]">{formatDate(entry.completed_at) ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
