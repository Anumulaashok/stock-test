import { describe, expect, it } from 'vitest'
import { topContributors, topDetractors } from './topContributorsDetractors'
import type { HoldingWithMarketData } from '../../types/backend'

function holding(overrides: Partial<HoldingWithMarketData> = {}): HoldingWithMarketData {
  return {
    id: 'h1', ticker: 'ACME', quantity: '10', average_cost: '100', added_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    current_price: '110', price_status: 'live', market_value: '1100', unrealized_gain: '100', unrealized_gain_percent: '10',
    ...overrides,
  }
}

describe('topContributors', () => {
  it('ranks positive-gain holdings by percent, highest first', () => {
    const holdings = [holding({ ticker: 'A', unrealized_gain_percent: '5' }), holding({ ticker: 'B', unrealized_gain_percent: '20' })]
    expect(topContributors(holdings).map((h) => h.ticker)).toEqual(['B', 'A'])
  })

  it('excludes negative and zero-gain holdings -- these are not contributors', () => {
    const holdings = [holding({ ticker: 'A', unrealized_gain_percent: '5' }), holding({ ticker: 'B', unrealized_gain_percent: '-10' }), holding({ ticker: 'C', unrealized_gain_percent: '0' })]
    expect(topContributors(holdings).map((h) => h.ticker)).toEqual(['A'])
  })

  it('excludes a holding with no live price, never sorting a null gain as zero', () => {
    const holdings = [holding({ ticker: 'A', unrealized_gain_percent: null, current_price: null, price_status: 'unavailable', market_value: null, unrealized_gain: null })]
    expect(topContributors(holdings)).toEqual([])
  })

  it('caps at the requested count', () => {
    const holdings = [1, 2, 3, 4].map((n) => holding({ ticker: `T${n}`, unrealized_gain_percent: String(n) }))
    expect(topContributors(holdings, 2)).toHaveLength(2)
  })
})

describe('topDetractors', () => {
  it('ranks negative-gain holdings by percent, most negative first', () => {
    const holdings = [holding({ ticker: 'A', unrealized_gain_percent: '-5' }), holding({ ticker: 'B', unrealized_gain_percent: '-20' })]
    expect(topDetractors(holdings).map((h) => h.ticker)).toEqual(['B', 'A'])
  })

  it('never overlaps with contributors on a small portfolio', () => {
    const holdings = [holding({ ticker: 'A', unrealized_gain_percent: '10' }), holding({ ticker: 'B', unrealized_gain_percent: '-10' })]
    const contributorTickers = topContributors(holdings).map((h) => h.ticker)
    const detractorTickers = topDetractors(holdings).map((h) => h.ticker)
    expect(contributorTickers.some((t) => detractorTickers.includes(t))).toBe(false)
  })
})
