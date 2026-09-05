import { describe, expect, it } from 'vitest'
import { watchlistToCsv } from './watchlistCsv'
import type { WatchlistItemEnriched } from '../../types/backend'

function item(overrides: Partial<WatchlistItemEnriched> = {}): WatchlistItemEnriched {
  return {
    ticker: 'ACME',
    created_at: '2026-08-01T00:00:00+00:00',
    current_price: '102.50',
    price_status: 'live',
    change_percent: '1.5',
    overall_score: '78',
    band: 'Attractive',
    last_researched_at: '2026-08-30T00:00:00+00:00',
    ...overrides,
  }
}

describe('watchlistToCsv', () => {
  it('includes the header row and one row per item', () => {
    const csv = watchlistToCsv([item()])
    const lines = csv.split('\r\n')
    expect(lines[0]).toBe('ticker,added_at,current_price,change_percent,overall_score,band,price_status,last_researched_at')
    expect(lines[1]).toBe('ACME,2026-08-01T00:00:00+00:00,102.50,1.5,78,Attractive,live,2026-08-30T00:00:00+00:00')
  })

  it('renders an unresearched ticker (null score/band) as empty fields, not zero', () => {
    const csv = watchlistToCsv([item({ overall_score: null, band: null, last_researched_at: null })])
    expect(csv).toContain('ACME,2026-08-01T00:00:00+00:00,102.50,1.5,,,live,')
  })

  it('renders zero items as just the header', () => {
    expect(watchlistToCsv([])).toBe(
      'ticker,added_at,current_price,change_percent,overall_score,band,price_status,last_researched_at',
    )
  })
})
