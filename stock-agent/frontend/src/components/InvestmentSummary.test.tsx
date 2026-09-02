import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { InvestmentSummary } from './InvestmentSummary'
import { buildReport } from '../test/fixtures'

function renderSummary(overrides: Parameters<typeof buildReport>[0] = {}) {
  return render(
    <InvestmentSummary
      report={buildReport(overrides)}
      authStatus="anonymous"
      inWatchlist={null}
      watchlistPending={false}
      watchlistError={null}
      onToggleWatchlist={vi.fn()}
    />,
  )
}

describe('InvestmentSummary', () => {
  it('renders the company identity, price, and signal', () => {
    renderSummary()
    expect(screen.getByRole('heading', { level: 1, name: 'Acme Corp' })).toBeInTheDocument()
    expect(screen.getByText('$100.00')).toBeInTheDocument()
    expect(screen.getByText('Strong')).toBeInTheDocument()
  })

  it('shows each calculated valuation method separately, never a blended fair value', () => {
    renderSummary()
    expect(screen.getByText('DCF fair value')).toBeInTheDocument()
    expect(screen.getByText('$140.00')).toBeInTheDocument()
    expect(screen.getByText(/40\.00% vs\. current price/)).toBeInTheDocument()
    // The unavailable P/E method must not appear as a figure in the summary.
    expect(screen.queryByText('P/E fair value')).not.toBeInTheDocument()
  })

  it('never hardcodes a buy/sell/hold/accumulate recommendation', () => {
    renderSummary()
    const text = document.body.textContent?.toLowerCase() ?? ''
    expect(text).not.toContain('buy')
    expect(text).not.toContain('sell')
    expect(text).not.toContain('accumulate')
    expect(text).not.toMatch(/\bhold\b/)
  })

  it('shows an anonymous watchlist hint rather than a fake local toggle', () => {
    renderSummary()
    expect(screen.getByTitle(/log in to save/i)).toBeInTheDocument()
  })
})
