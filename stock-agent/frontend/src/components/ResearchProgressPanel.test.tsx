import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ResearchProgressPanel } from './ResearchProgressPanel'
import * as researchApi from '../api/research'
import type { ResearchProgress } from '../types/backend'

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

function buildProgress(overrides: Partial<ResearchProgress> = {}): ResearchProgress {
  return {
    ticker: 'ACME',
    research_run_id: null,
    finished: false,
    stages: [
      { key: 'financials', label: 'Fetching financial statements', status: 'success', detail: null },
      { key: 'market', label: 'Fetching market data', status: 'running', detail: null },
      { key: 'analysis', label: 'Running financial analysis, valuation & scoring', status: 'pending', detail: null },
      { key: 'analyst', label: 'Generating AI analyst commentary', status: 'pending', detail: null },
      { key: 'report', label: 'Generating report', status: 'pending', detail: null },
      { key: 'saving', label: 'Saving results', status: 'pending', detail: null },
    ],
    ...overrides,
  }
}

describe('ResearchProgressPanel', () => {
  it('shows a plain starting message before any progress is known (404)', async () => {
    vi.spyOn(researchApi, 'fetchResearchProgress').mockResolvedValue(null)
    render(<ResearchProgressPanel ticker="ACME" />)

    expect(await screen.findByText(/starting research/i)).toBeInTheDocument()
  })

  it('renders every real stage label once progress is known', async () => {
    vi.spyOn(researchApi, 'fetchResearchProgress').mockResolvedValue(buildProgress())
    render(<ResearchProgressPanel ticker="ACME" />)

    expect(await screen.findByText('Fetching financial statements')).toBeInTheDocument()
    expect(screen.getByText('Fetching market data')).toBeInTheDocument()
    expect(screen.getByText('Running financial analysis, valuation & scoring')).toBeInTheDocument()
    expect(screen.getByText('Generating AI analyst commentary')).toBeInTheDocument()
    expect(screen.getByText('Generating report')).toBeInTheDocument()
    expect(screen.getByText('Saving results')).toBeInTheDocument()
  })

  it('shows the failure detail for a failed stage', async () => {
    vi.spyOn(researchApi, 'fetchResearchProgress').mockResolvedValue(
      buildProgress({
        stages: [
          { key: 'financials', label: 'Fetching financial statements', status: 'failed', detail: 'Provider unavailable' },
        ],
      }),
    )
    render(<ResearchProgressPanel ticker="ACME" />)

    expect(await screen.findByText('Provider unavailable')).toBeInTheDocument()
  })

  it('polls again after the first response when not yet finished', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const spy = vi
      .spyOn(researchApi, 'fetchResearchProgress')
      .mockResolvedValueOnce(buildProgress({ finished: false }))
      .mockResolvedValueOnce(buildProgress({ finished: true }))

    render(<ResearchProgressPanel ticker="ACME" />)
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))

    await vi.advanceTimersByTimeAsync(1300)
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2))
  })

  it('stops polling once the run is finished', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const spy = vi.spyOn(researchApi, 'fetchResearchProgress').mockResolvedValue(buildProgress({ finished: true }))

    render(<ResearchProgressPanel ticker="ACME" />)
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))

    await vi.advanceTimersByTimeAsync(5000)
    expect(spy).toHaveBeenCalledTimes(1)
  })
})
