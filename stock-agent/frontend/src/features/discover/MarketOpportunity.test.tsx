import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, afterEach } from 'vitest'
import { MarketOpportunity } from './MarketOpportunity'
import { renderWithRouter } from '../../test/renderWithRouter'
import type { MarketOpportunityResult, SectorStockSummary, SectorSummary } from '../../types/backend'

vi.mock('../../api/sectors', () => ({ fetchMarketOpportunity: vi.fn() }))
const { fetchMarketOpportunity } = await import('../../api/sectors')
const mocked = vi.mocked(fetchMarketOpportunity)

afterEach(() => vi.resetAllMocks())

function buildStock(overrides: Partial<SectorStockSummary> = {}): SectorStockSummary {
  return {
    ticker: 'ACME',
    company_name: 'Acme Corp',
    overall_score: '78',
    band: 'good',
    status: 'calculated',
    ...overrides,
  }
}

function buildSector(overrides: Partial<SectorSummary> = {}): SectorSummary {
  return {
    sector: 'Technology',
    sector_score: '82',
    outlook: 'bullish',
    risk: 'low',
    growth_score: '75',
    valuation_score: '60',
    momentum_score: '70',
    news_headline_count: 3,
    constituents_evaluated: 8,
    constituents_total: 10,
    top_stocks: [buildStock()],
    ...overrides,
  }
}

function buildResult(overrides: Partial<MarketOpportunityResult> = {}): MarketOpportunityResult {
  return {
    status: 'success',
    generated_at: '2026-03-01T10:00:00+00:00',
    sectors: [buildSector()],
    warnings: [],
    ...overrides,
  }
}

describe('MarketOpportunity', () => {
  it('renders sectors ranked, with the first sector selected and its stocks listed', async () => {
    mocked.mockResolvedValue(
      buildResult({
        sectors: [
          buildSector({ sector: 'Technology', top_stocks: [buildStock({ ticker: 'ACME' })] }),
          buildSector({ sector: 'Energy', top_stocks: [buildStock({ ticker: 'FUEL', company_name: 'Fuel Co' })] }),
        ],
      }),
    )

    renderWithRouter(<MarketOpportunity />)

    expect(await screen.findByText('Technology')).toBeInTheDocument()
    expect(screen.getByText('Energy')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Top stocks · Technology/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'ACME' })).toHaveAttribute('href', '/stock/ACME')
    expect(screen.queryByText('FUEL')).not.toBeInTheDocument()
  })

  it('switches the stock table when a different sector card is selected', async () => {
    mocked.mockResolvedValue(
      buildResult({
        sectors: [
          buildSector({ sector: 'Technology', top_stocks: [buildStock({ ticker: 'ACME' })] }),
          buildSector({ sector: 'Energy', top_stocks: [buildStock({ ticker: 'FUEL', company_name: 'Fuel Co' })] }),
        ],
      }),
    )

    renderWithRouter(<MarketOpportunity />)
    await screen.findByText('Technology')

    await userEvent.click(screen.getByRole('button', { name: /Energy/ }))

    expect(screen.getByRole('heading', { name: /Top stocks · Energy/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'FUEL' })).toBeInTheDocument()
  })

  it('shows "Unavailable" rather than a fabricated score when fields are null', async () => {
    mocked.mockResolvedValue(
      buildResult({
        sectors: [
          buildSector({
            sector_score: null,
            growth_score: null,
            top_stocks: [buildStock({ ticker: 'DOWN', status: 'unavailable', overall_score: null, band: null })],
          }),
        ],
      }),
    )

    renderWithRouter(<MarketOpportunity />)
    await screen.findByText('Technology')

    expect(screen.getByText('Score unavailable')).toBeInTheDocument()
    const row = screen.getByRole('link', { name: 'DOWN' }).closest('tr')!
    expect(within(row).getAllByText('Unavailable').length).toBeGreaterThan(0)
  })

  it('shows an honest message when sector ranking is unavailable, with no sector cards', async () => {
    mocked.mockResolvedValue(buildResult({ status: 'unavailable', sectors: [] }))

    renderWithRouter(<MarketOpportunity />)

    expect(await screen.findByText(/Sector ranking is unavailable/)).toBeInTheDocument()
  })

  it('requests a forced refresh when Refresh is clicked', async () => {
    mocked.mockResolvedValue(buildResult())

    renderWithRouter(<MarketOpportunity />)
    await screen.findByText('Technology')
    expect(mocked).toHaveBeenLastCalledWith(false)

    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))

    await waitFor(() => expect(mocked).toHaveBeenLastCalledWith(true))
  })

  it('lets the user retry after a failed load', async () => {
    mocked.mockRejectedValueOnce(new Error('network down'))
    mocked.mockResolvedValueOnce(buildResult())

    renderWithRouter(<MarketOpportunity />)

    expect(await screen.findByText('Could not load sector rankings')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))

    expect(await screen.findByText('Technology')).toBeInTheDocument()
  })
})
