import type { RecentResearchEntry, ScoreBand } from '../../types/backend'

export type ScreenerSort = 'score_desc' | 'score_asc' | 'ticker_asc' | 'date_desc'

export interface ScreenerFilters {
  bands: ScoreBand[]
  minScore: number | null
  sort: ScreenerSort
}

export const DEFAULT_FILTERS: ScreenerFilters = { bands: [], minScore: null, sort: 'score_desc' }

export function filtersToSearchParams(filters: ScreenerFilters): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.bands.length > 0) params.set('bands', filters.bands.join(','))
  if (filters.minScore !== null) params.set('minScore', String(filters.minScore))
  if (filters.sort !== DEFAULT_FILTERS.sort) params.set('sort', filters.sort)
  return params
}

const VALID_SORTS: ScreenerSort[] = ['score_desc', 'score_asc', 'ticker_asc', 'date_desc']
const VALID_BANDS: ScoreBand[] = ['excellent', 'strong', 'good', 'fair', 'weak', 'poor']

export function filtersFromSearchParams(params: URLSearchParams): ScreenerFilters {
  const bandsParam = params.get('bands')
  const bands = bandsParam ? (bandsParam.split(',').filter((b): b is ScoreBand => VALID_BANDS.includes(b as ScoreBand))) : []
  const minScoreParam = params.get('minScore')
  const minScore = minScoreParam !== null && Number.isFinite(Number(minScoreParam)) ? Number(minScoreParam) : null
  const sortParam = params.get('sort')
  const sort = sortParam && VALID_SORTS.includes(sortParam as ScreenerSort) ? (sortParam as ScreenerSort) : DEFAULT_FILTERS.sort
  return { bands, minScore, sort }
}

/** Reshapes/filters entries the backend already returned -- never
 * fabricates a score for a null one. A row with no score is excluded
 * by a min-score or band filter (it can't satisfy either honestly),
 * but stays visible with no filter active. */
export function filterEntries(entries: RecentResearchEntry[], filters: ScreenerFilters): RecentResearchEntry[] {
  return entries.filter((e) => {
    if (filters.bands.length > 0 && (e.band === null || !filters.bands.includes(e.band as ScoreBand))) return false
    if (filters.minScore !== null) {
      if (e.overall_score === null) return false
      const score = Number(e.overall_score)
      if (!Number.isFinite(score) || score < filters.minScore) return false
    }
    return true
  })
}

export function sortEntries(entries: RecentResearchEntry[], sort: ScreenerSort): RecentResearchEntry[] {
  const withScore = (e: RecentResearchEntry) => (e.overall_score !== null ? Number(e.overall_score) : null)
  const sorted = [...entries]
  switch (sort) {
    case 'score_desc':
      return sorted.sort((a, b) => (withScore(b) ?? -Infinity) - (withScore(a) ?? -Infinity))
    case 'score_asc':
      return sorted.sort((a, b) => (withScore(a) ?? Infinity) - (withScore(b) ?? Infinity))
    case 'ticker_asc':
      return sorted.sort((a, b) => a.ticker.localeCompare(b.ticker))
    case 'date_desc':
      return sorted.sort((a, b) => (b.completed_at ?? '').localeCompare(a.completed_at ?? ''))
  }
}

/** Names the filter responsible for an empty result, for an honest
 * empty state -- never a generic "no results." */
export function describeActiveFilters(filters: ScreenerFilters): string | null {
  const parts: string[] = []
  if (filters.bands.length > 0) parts.push(`band in ${filters.bands.join(', ')}`)
  if (filters.minScore !== null) parts.push(`score ≥ ${filters.minScore}`)
  return parts.length > 0 ? parts.join(' and ') : null
}
