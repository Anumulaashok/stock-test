import { describe, expect, it } from 'vitest'
import { holdingsToCsv } from './portfolioCsv'
import type { HoldingWithMarketData } from '../../types/backend'

function holding(overrides: Partial<HoldingWithMarketData> = {}): HoldingWithMarketData {
  return {
    id: 'h1',
    ticker: 'ACME',
    quantity: '10',
    average_cost: '100.00',
    added_at: '2026-08-01T00:00:00+00:00',
    updated_at: '2026-08-01T00:00:00+00:00',
    current_price: '110.00',
    price_status: 'live',
    market_value: '1100.00',
    unrealized_gain: '100.00',
    unrealized_gain_percent: '10.0',
    ...overrides,
  }
}

describe('holdingsToCsv', () => {
  it('includes the header row and one row per holding', () => {
    const csv = holdingsToCsv([holding()])
    const lines = csv.split('\r\n')
    expect(lines[0]).toBe('ticker,quantity,average_cost,current_price,price_status,market_value,unrealized_gain,unrealized_gain_percent')
    expect(lines[1]).toBe('ACME,10,100.00,110.00,live,1100.00,100.00,10.0')
  })

  it('renders an unpriceable holding (null market data) as empty fields, not zero', () => {
    const csv = holdingsToCsv([
      holding({ current_price: null, price_status: 'unavailable', market_value: null, unrealized_gain: null, unrealized_gain_percent: null }),
    ])
    expect(csv).toContain('ACME,10,100.00,,unavailable,,,')
  })

  it('renders zero holdings as just the header', () => {
    expect(holdingsToCsv([])).toBe(
      'ticker,quantity,average_cost,current_price,price_status,market_value,unrealized_gain,unrealized_gain_percent',
    )
  })
})
