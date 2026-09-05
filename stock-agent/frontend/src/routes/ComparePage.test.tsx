import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ComparePage } from './ComparePage'
import { renderWithRouter } from '../test/renderWithRouter'
import * as researchApi from '../api/research'
import { buildReport, buildRunResult } from '../test/fixtures'

describe('ComparePage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('asks for at least two tickers rather than rendering an empty table', () => {
    renderWithRouter(<ComparePage />, { initialEntries: ['/compare?tickers=ACME'] })
    expect(screen.getByText(/add at least two tickers/i)).toBeInTheDocument()
  })

  it('fetches each ticker once and renders aligned rows', async () => {
    const fetchSpy = vi.spyOn(researchApi, 'fetchLatestResearch').mockImplementation(async (ticker) =>
      buildRunResult(
        buildReport({
          company: { name: ticker, ticker, currency: null },
          summary: { overall_score: ticker === 'ACME' ? '80' : '60', overall_status: 'calculated', score_band: 'good', signal: null, investment_thesis: null, key_takeaways: [] },
        }),
      ),
    )

    renderWithRouter(<ComparePage />, { initialEntries: ['/compare?tickers=acme,beta'] })

    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2))
    expect(fetchSpy).toHaveBeenCalledWith('ACME')
    expect(fetchSpy).toHaveBeenCalledWith('BETA')
    expect(await screen.findByText('80')).toBeInTheDocument()
    expect(screen.getByText('60')).toBeInTheDocument()
  })

  it('shows Unavailable, never blank or borrowed from a sibling, for a never-researched ticker', async () => {
    vi.spyOn(researchApi, 'fetchLatestResearch').mockImplementation(async (ticker) =>
      ticker === 'ACME' ? buildRunResult(buildReport()) : null,
    )

    renderWithRouter(<ComparePage />, { initialEntries: ['/compare?tickers=ACME,NEVERRESEARCHED'] })

    expect(await screen.findAllByText('Unavailable')).not.toHaveLength(0)
  })

  it('deduplicates and caps at 4 tickers', async () => {
    const fetchSpy = vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(null)
    renderWithRouter(<ComparePage />, { initialEntries: ['/compare?tickers=A,A,B,C,D,E'] })
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(4))
  })
})
