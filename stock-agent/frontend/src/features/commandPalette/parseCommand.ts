import { filtersToSearchParams, DEFAULT_FILTERS, type ScreenerFilters } from '../screener/screenerFilters'
import { paths } from '../../routes/paths'
import type { ScoreBand } from '../../types/backend'

export interface ParsedCommand {
  path: string
  description: string
}

export interface CommandError {
  error: string
}

const KNOWN_PAGES: Record<string, () => string> = {
  discover: paths.discover,
  screener: paths.screener,
  watchlist: paths.watchlist,
  portfolio: paths.portfolio,
  alerts: paths.alerts,
  research: paths.research,
  home: paths.home,
}

const VALID_BANDS: ScoreBand[] = ['excellent', 'strong', 'good', 'fair', 'weak', 'poor']

function parseCompare(rest: string): ParsedCommand | CommandError {
  const tickers = rest
    .split(/[\s,]+/)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean)
  if (tickers.length < 2 || tickers.length > 4) {
    return { error: 'compare needs 2-4 tickers, e.g. "compare TCS INFY"' }
  }
  return { path: paths.compare(tickers), description: `Compare ${tickers.join(', ')}` }
}

function parseScreen(rest: string): ParsedCommand | CommandError {
  const filters: ScreenerFilters = { ...DEFAULT_FILTERS }
  const unsupported: string[] = []
  const tokens = rest.split(/\s+/).filter(Boolean)
  for (const token of tokens) {
    const scoreMatch = token.match(/^score\s*(>=|>)\s*(\d+(?:\.\d+)?)$/i)
    if (scoreMatch) {
      filters.minScore = Number(scoreMatch[2])
      continue
    }
    const bandMatch = token.match(/^band:(.+)$/i)
    if (bandMatch) {
      const requested = bandMatch[1].split(',').map((b) => b.trim().toLowerCase())
      const valid = requested.filter((b): b is ScoreBand => VALID_BANDS.includes(b as ScoreBand))
      filters.bands = [...filters.bands, ...valid]
      continue
    }
    unsupported.push(token)
  }
  if (unsupported.length > 0) {
    return {
      error: `"${unsupported.join(' ')}" isn't a supported screener filter yet -- only score>N and band:X (${VALID_BANDS.join('/')}) are wired up`,
    }
  }
  const query = filtersToSearchParams(filters).toString()
  return { path: query ? `${paths.screener()}?${query}` : paths.screener(), description: 'Screen with these filters' }
}

/** Parses a ⌘K command into an existing route -- never invents a new
 * page or a filter the Screener doesn't actually support (sector/ROE
 * thresholds are logged in BACKLOG.md, not silently accepted here). */
export function parseCommand(input: string): ParsedCommand | CommandError | null {
  const trimmed = input.trim()
  if (!trimmed) return null

  const [head, ...restParts] = trimmed.split(/\s+/)
  const rest = restParts.join(' ')
  const headLower = head.toLowerCase()

  if (headLower === 'compare' && rest) return parseCompare(rest)
  if (headLower === 'screen') return parseScreen(rest)
  if (headLower in KNOWN_PAGES && !rest) return { path: KNOWN_PAGES[headLower](), description: `Go to ${head}` }

  const bareTicker = trimmed.toUpperCase()
  if (/^[A-Z0-9.&-]{1,20}$/.test(bareTicker) && !bareTicker.includes(' ')) {
    return { path: paths.stock(bareTicker), description: `Open ${bareTicker}` }
  }

  return { error: `Not recognized. Try a ticker, "compare A B", "screen score>70 band:strong", or a page name.` }
}
