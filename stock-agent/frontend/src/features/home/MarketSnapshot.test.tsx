import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MarketSnapshot } from './MarketSnapshot'
import * as marketHistoryApi from '../../api/marketHistory'
import type { IndexQuote } from '../../types/backend'

afterEach(() => vi.restoreAllMocks())

function quote(overrides: Partial<IndexQuote> = {}): IndexQuote {
  return {
    name: 'Nifty 50',
    symbol: '^NSEI',
    status: 'available',
    current_price: '24500.35',
    previous_close: '24300.10',
    change: '200.25',
    change_percent: '0.82',
    source: 'yfinance',
    freshness: 'live',
    warning: null,
    ...overrides,
  }
}

describe('MarketSnapshot', () => {
  it('renders real index levels with a positive change', async () => {
    vi.spyOn(marketHistoryApi, 'fetchIndexQuotes').mockResolvedValue({ indices: [quote()] })

    render(<MarketSnapshot />)

    expect(await screen.findByText('Nifty 50')).toBeInTheDocument()
    expect(screen.getByText('24500.35')).toBeInTheDocument()
    expect(screen.getByText('+0.82%')).toBeInTheDocument()
  })

  it('shows an honest Unavailable badge instead of a fabricated value', async () => {
    vi.spyOn(marketHistoryApi, 'fetchIndexQuotes').mockResolvedValue({
      indices: [quote({ status: 'unavailable', current_price: null, change_percent: null, warning: 'Provider timed out' })],
    })

    render(<MarketSnapshot />)

    expect(await screen.findByText('Unavailable')).toBeInTheDocument()
    expect(screen.getByText('— . —')).toBeInTheDocument()
  })

  it('surfaces a real error instead of failing silently', async () => {
    vi.spyOn(marketHistoryApi, 'fetchIndexQuotes').mockRejectedValue(new Error('network'))

    render(<MarketSnapshot />)

    expect(await screen.findByText('Could not load market data')).toBeInTheDocument()
  })
})
