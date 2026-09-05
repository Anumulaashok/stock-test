import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ScreenerPage } from './ScreenerPage'
import { renderWithRouter } from '../test/renderWithRouter'
import * as researchApi from '../api/research'
import * as csvLib from '../lib/csv'
import type { RecentResearchEntry } from '../types/backend'

function entry(overrides: Partial<RecentResearchEntry> = {}): RecentResearchEntry {
  return {
    ticker: 'ACME', company_name: 'Acme Corp', research_run_id: 'r1', research_date: '2026-08-01',
    status: 'COMPLETED', run_type: 'NORMAL', overall_score: '78', band: 'good', completed_at: '2026-08-01T00:00:00+00:00',
    ...overrides,
  }
}

describe('ScreenerPage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('lists the tracked tickers with score and band', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([entry(), entry({ ticker: 'BETA', overall_score: '55', band: 'fair' })])
    renderWithRouter(<ScreenerPage />)

    expect(await screen.findByText('ACME')).toBeInTheDocument()
    expect(screen.getByText('BETA')).toBeInTheDocument()
    expect(screen.getByText('78')).toBeInTheDocument()
  })

  it('shows "Not scored," never a fabricated 0, for a null score', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([entry({ overall_score: null, band: null })])
    renderWithRouter(<ScreenerPage />)

    expect(await screen.findByText(/not scored/i)).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('filters by band and updates the URL', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([entry({ ticker: 'A', band: 'good' }), entry({ ticker: 'B', band: 'poor' })])
    renderWithRouter(<ScreenerPage />)
    await screen.findByText('A')

    await userEvent.click(screen.getByRole('button', { name: 'good' }))

    await waitFor(() => expect(screen.queryByText('B')).not.toBeInTheDocument())
    expect(screen.getByText('A')).toBeInTheDocument()
  })

  it('names the active filter in the empty-result state', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([entry({ band: 'good' })])
    renderWithRouter(<ScreenerPage />)
    await screen.findByText('ACME')

    await userEvent.click(screen.getByRole('button', { name: 'poor' }))

    expect(await screen.findByText(/no tracked ticker matches: band in poor/i)).toBeInTheDocument()
  })

  it('exports the filtered rows as CSV', async () => {
    const downloadSpy = vi.spyOn(csvLib, 'downloadCsv').mockImplementation(() => {})
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([entry()])
    renderWithRouter(<ScreenerPage />)
    await screen.findByText('ACME')

    await userEvent.click(screen.getByRole('button', { name: /export csv/i }))
    expect(downloadSpy).toHaveBeenCalledWith('screener', expect.stringContaining('ACME'))
  })

  it('sorts by ticker when selected', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([entry({ ticker: 'ZETA' }), entry({ ticker: 'ALPHA' })])
    renderWithRouter(<ScreenerPage />)
    await screen.findByText('ZETA')

    await userEvent.selectOptions(screen.getByLabelText(/sort by/i), 'Ticker (A-Z)')

    const rows = screen.getAllByRole('row').slice(1) // drop header row
    expect(rows[0]).toHaveTextContent('ALPHA')
  })
})
