import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderWithRouter } from '../test/renderWithRouter'
import { PortfolioPage } from './PortfolioPage'
import * as portfolioApi from '../api/portfolio'
import { ApiError } from '../api/client'
import * as csvLib from '../lib/csv'
import type { PortfolioSummary } from '../types/backend'

function buildSummary(overrides: Partial<PortfolioSummary> = {}): PortfolioSummary {
  return {
    portfolio_id: 'p1',
    invested_capital: '1000',
    portfolio_value: '1200',
    unrealized_gain: '200',
    unrealized_gain_percent: '20',
    warnings: [],
    holdings: [
      {
        id: 'h1',
        ticker: 'ACME',
        quantity: '10',
        average_cost: '100',
        added_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        current_price: '120',
        price_status: 'live',
        market_value: '1200',
        unrealized_gain: '200',
        unrealized_gain_percent: '20',
      },
    ],
    ...overrides,
  }
}

describe('PortfolioPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows the summary stats and holdings once loaded', async () => {
    vi.spyOn(portfolioApi, 'fetchPortfolioSummary').mockResolvedValue(buildSummary())
    renderWithRouter(<PortfolioPage />)

    expect((await screen.findAllByText('ACME')).length).toBeGreaterThan(0)
    expect(screen.getByText(/₹1,000/)).toBeInTheDocument()
  })

  it('shows a table-shaped skeleton (not generic bare lines) while loading', () => {
    vi.spyOn(portfolioApi, 'fetchPortfolioSummary').mockReturnValue(new Promise(() => {}))
    renderWithRouter(<PortfolioPage />)

    expect(screen.getByRole('status', { name: /loading holdings/i })).toBeInTheDocument()
  })

  it('shows an error state with retry on load failure', async () => {
    vi.spyOn(portfolioApi, 'fetchPortfolioSummary').mockRejectedValue(new ApiError('down', 'server', 500))
    renderWithRouter(<PortfolioPage />)

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('exports holdings as CSV on click', async () => {
    const downloadSpy = vi.spyOn(csvLib, 'downloadCsv').mockImplementation(() => {})
    vi.spyOn(portfolioApi, 'fetchPortfolioSummary').mockResolvedValue(buildSummary())
    renderWithRouter(<PortfolioPage />)
    await screen.findAllByText('ACME')

    await userEvent.click(screen.getByRole('button', { name: /export csv/i }))

    expect(downloadSpy).toHaveBeenCalledWith('portfolio', expect.stringContaining('ACME'))
  })

  it('disables CSV export when there are no holdings', async () => {
    vi.spyOn(portfolioApi, 'fetchPortfolioSummary').mockResolvedValue(buildSummary({ holdings: [] }))
    renderWithRouter(<PortfolioPage />)
    await screen.findByText(/no holdings yet/i)

    expect(screen.getByRole('button', { name: /export csv/i })).toBeDisabled()
  })

  it('shows an honest empty state with no invented sector/allocation data', async () => {
    vi.spyOn(portfolioApi, 'fetchPortfolioSummary').mockResolvedValue(buildSummary({ holdings: [] }))
    renderWithRouter(<PortfolioPage />)

    expect(await screen.findByText(/no holdings yet/i)).toBeInTheDocument()
    expect(screen.queryByText(/sector/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/allocation/i)).not.toBeInTheDocument()
  })

  it('focuses the add-holding ticker input when the empty state\'s one-click button is clicked', async () => {
    vi.spyOn(portfolioApi, 'fetchPortfolioSummary').mockResolvedValue(buildSummary({ holdings: [] }))
    renderWithRouter(<PortfolioPage />)
    await screen.findByText(/no holdings yet/i)

    await userEvent.click(screen.getByRole('button', { name: /add your first holding/i }))

    expect(screen.getByLabelText(/^ticker$/i)).toHaveFocus()
  })

  it('reloads the summary after adding a holding', async () => {
    const fetchSpy = vi
      .spyOn(portfolioApi, 'fetchPortfolioSummary')
      .mockResolvedValueOnce(buildSummary({ holdings: [] }))
      .mockResolvedValueOnce(buildSummary())
    vi.spyOn(portfolioApi, 'addHolding').mockResolvedValue({
      id: 'h1',
      ticker: 'ACME',
      quantity: '10',
      average_cost: '100',
      added_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })

    renderWithRouter(<PortfolioPage />)
    await screen.findByText(/no holdings yet/i)

    await userEvent.type(screen.getByLabelText(/^ticker$/i), 'ACME')
    await userEvent.type(screen.getByLabelText(/quantity/i), '10')
    await userEvent.type(screen.getByLabelText(/avg cost/i), '100')
    await userEvent.click(screen.getByRole('button', { name: /add holding/i }))

    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2))
    expect((await screen.findAllByText('ACME')).length).toBeGreaterThan(0)
  })

  it('reloads the summary after deleting a holding', async () => {
    const fetchSpy = vi
      .spyOn(portfolioApi, 'fetchPortfolioSummary')
      .mockResolvedValueOnce(buildSummary())
      .mockResolvedValueOnce(buildSummary({ holdings: [] }))
    vi.spyOn(portfolioApi, 'deleteHolding').mockResolvedValue(undefined)

    renderWithRouter(<PortfolioPage />)
    await screen.findAllByText('ACME')

    await userEvent.click(screen.getByRole('button', { name: /remove/i }))

    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2))
    expect(await screen.findByText(/no holdings yet/i)).toBeInTheDocument()
  })
})
