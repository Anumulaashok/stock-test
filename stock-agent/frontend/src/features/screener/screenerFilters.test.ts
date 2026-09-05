import { describe, expect, it } from 'vitest'
import {
  DEFAULT_FILTERS,
  describeActiveFilters,
  filterEntries,
  filtersFromSearchParams,
  filtersToSearchParams,
  sortEntries,
  type ScreenerFilters,
} from './screenerFilters'
import type { RecentResearchEntry } from '../../types/backend'

function entry(overrides: Partial<RecentResearchEntry> = {}): RecentResearchEntry {
  return {
    ticker: 'ACME', company_name: 'Acme Corp', research_run_id: 'r1', research_date: '2026-08-01',
    status: 'COMPLETED', run_type: 'NORMAL', overall_score: '78', band: 'good', completed_at: '2026-08-01T00:00:00+00:00',
    ...overrides,
  }
}

describe('filtersToSearchParams / filtersFromSearchParams', () => {
  it('round-trips filters through URL params', () => {
    const filters: ScreenerFilters = { bands: ['good', 'strong'], minScore: 70, sort: 'ticker_asc' }
    const params = filtersToSearchParams(filters)
    expect(filtersFromSearchParams(params)).toEqual({ bands: ['good', 'strong'], minScore: 70, sort: 'ticker_asc' })
  })

  it('produces no params for the default filter state', () => {
    expect(filtersToSearchParams(DEFAULT_FILTERS).toString()).toBe('')
  })

  it('ignores an invalid band or sort value from the URL rather than crashing', () => {
    const params = new URLSearchParams('bands=not-a-real-band,good&sort=nonsense')
    expect(filtersFromSearchParams(params)).toEqual({ bands: ['good'], minScore: null, sort: 'score_desc' })
  })
})

describe('filterEntries', () => {
  it('excludes a null-score row when a min-score filter is active, never fabricating a score for it', () => {
    const entries = [entry({ ticker: 'A', overall_score: '80' }), entry({ ticker: 'B', overall_score: null, band: null })]
    const result = filterEntries(entries, { bands: [], minScore: 50, sort: 'score_desc' })
    expect(result.map((e) => e.ticker)).toEqual(['A'])
  })

  it('shows a null-score row when no score filter is active', () => {
    const entries = [entry({ ticker: 'A', overall_score: null, band: null })]
    expect(filterEntries(entries, DEFAULT_FILTERS)).toHaveLength(1)
  })

  it('filters by band', () => {
    const entries = [entry({ ticker: 'A', band: 'good' }), entry({ ticker: 'B', band: 'poor' })]
    const result = filterEntries(entries, { bands: ['good'], minScore: null, sort: 'score_desc' })
    expect(result.map((e) => e.ticker)).toEqual(['A'])
  })
})

describe('sortEntries', () => {
  it('sorts by score descending, treating a missing score as lowest', () => {
    const entries = [entry({ ticker: 'A', overall_score: '50' }), entry({ ticker: 'B', overall_score: '90' }), entry({ ticker: 'C', overall_score: null })]
    expect(sortEntries(entries, 'score_desc').map((e) => e.ticker)).toEqual(['B', 'A', 'C'])
  })

  it('sorts by ticker alphabetically', () => {
    const entries = [entry({ ticker: 'ZETA' }), entry({ ticker: 'ALPHA' })]
    expect(sortEntries(entries, 'ticker_asc').map((e) => e.ticker)).toEqual(['ALPHA', 'ZETA'])
  })

  it('does not mutate the input array', () => {
    const entries = [entry({ ticker: 'B' }), entry({ ticker: 'A' })]
    const original = [...entries]
    sortEntries(entries, 'ticker_asc')
    expect(entries).toEqual(original)
  })
})

describe('describeActiveFilters', () => {
  it('names the active filters for an honest empty state', () => {
    expect(describeActiveFilters({ bands: ['good'], minScore: 90, sort: 'score_desc' })).toBe('band in good and score ≥ 90')
  })

  it('returns null when nothing is filtered', () => {
    expect(describeActiveFilters(DEFAULT_FILTERS)).toBeNull()
  })
})
