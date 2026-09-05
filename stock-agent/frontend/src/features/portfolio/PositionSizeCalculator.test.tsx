import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PositionSizeCalculator } from './PositionSizeCalculator'
import * as researchApi from '../../api/research'
import { buildReport, buildRunResult } from '../../test/fixtures'

describe('PositionSizeCalculator', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('is always labeled SCENARIO', () => {
    render(<PositionSizeCalculator />)
    expect(screen.getByText('Scenario')).toBeInTheDocument()
  })

  it('never renders a buy/sell/execute affordance (I3)', () => {
    render(<PositionSizeCalculator />)
    expect(screen.queryByRole('button', { name: /buy|sell|execute|place order/i })).not.toBeInTheDocument()
  })

  it('shows a placeholder, not a fabricated result, until valid inputs are entered', () => {
    render(<PositionSizeCalculator />)
    expect(screen.getByText(/enter an account size/i)).toBeInTheDocument()
  })

  it('computes shares/position value/risk amount from valid inputs', async () => {
    render(<PositionSizeCalculator />)
    await userEvent.type(screen.getByLabelText(/account size/i), '100000')
    await userEvent.clear(screen.getByLabelText(/risk % of account/i))
    await userEvent.type(screen.getByLabelText(/risk % of account/i), '1')
    await userEvent.type(screen.getByLabelText(/entry price/i), '100')
    await userEvent.type(screen.getByLabelText(/stop price/i), '90')

    expect(screen.getByText('100')).toBeInTheDocument() // share count
  })

  it('looks up the real current price and fills it into the entry price field', async () => {
    vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(
      buildRunResult(buildReport({ market: { source: 'yfinance', current_price: '2500', previous_close: '2490', change: '10', change_percent: '0.4', currency: 'INR', market_status: 'open', market_timestamp: null, freshness: 'live', market_cap: null, year_high: null, year_low: null, formatted_current_price: '₹2,500.00' } })),
    )
    render(<PositionSizeCalculator />)

    await userEvent.type(screen.getByLabelText(/ticker/i), 'acme')
    await userEvent.click(screen.getByRole('button', { name: /look up price/i }))

    expect(await screen.findByText(/current price: ₹2,500.00/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/entry price/i)).toHaveValue('2500')
  })

  it('shows a real error, not a silent failure, when no live price exists', async () => {
    vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(buildRunResult(buildReport({ market: null })))
    render(<PositionSizeCalculator />)

    await userEvent.type(screen.getByLabelText(/ticker/i), 'acme')
    await userEvent.click(screen.getByRole('button', { name: /look up price/i }))

    expect(await screen.findByText(/no live price available/i)).toBeInTheDocument()
  })
})
