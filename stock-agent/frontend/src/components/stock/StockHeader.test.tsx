import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StockHeader } from './StockHeader'
import { buildReport } from '../../test/fixtures'

describe('StockHeader', () => {
  it('renders company, ticker, price, and change from the market section', () => {
    const report = buildReport()
    render(
      <StockHeader
        company={report.company}
        market={report.market}
        authStatus="anonymous"
        inWatchlist={null}
        watchlistPending={false}
        watchlistError={null}
        onToggleWatchlist={vi.fn()}
      />,
    )
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    expect(screen.getByText('ACME')).toBeInTheDocument()
    expect(screen.getByText('₹100.00')).toBeInTheDocument()
    expect(screen.getByText('+2.4%')).toBeInTheDocument()
  })

  it('shows an explicit unavailable state instead of a blank or zero price when market data is absent', () => {
    const report = buildReport({ market: null })
    render(
      <StockHeader
        company={report.company}
        market={report.market}
        authStatus="anonymous"
        inWatchlist={null}
        watchlistPending={false}
        watchlistError={null}
        onToggleWatchlist={vi.fn()}
      />,
    )
    expect(screen.getByText('Price unavailable')).toBeInTheDocument()
  })
})
