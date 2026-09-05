import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { RecentResearch } from './RecentResearch'
import * as researchApi from '../../api/research'
import type { RecentResearchEntry } from '../../types/backend'

afterEach(() => {
  vi.restoreAllMocks()
})

function renderIt() {
  return render(
    <MemoryRouter>
      <RecentResearch />
    </MemoryRouter>,
  )
}

function entry(overrides: Partial<RecentResearchEntry> = {}): RecentResearchEntry {
  return {
    ticker: 'TCS',
    company_name: 'Tata Consultancy Services',
    research_run_id: 'run-1',
    research_date: '2026-09-02',
    status: 'COMPLETED',
    run_type: 'NORMAL',
    overall_score: '78',
    band: 'good',
    completed_at: '2026-09-02T10:00:00Z',
    ...overrides,
  }
}

describe('RecentResearch', () => {
  it('renders for an anonymous viewer -- research is global, not per-user', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([entry()])

    renderIt()

    expect(await screen.findByText('TCS')).toBeInTheDocument()
    expect(screen.getByText('Tata Consultancy Services')).toBeInTheDocument()
  })

  it('makes exactly one request regardless of how many tickers exist', async () => {
    const spy = vi
      .spyOn(researchApi, 'fetchRecentResearch')
      .mockResolvedValue([entry({ ticker: 'A' }), entry({ ticker: 'B' }), entry({ ticker: 'C' })])

    renderIt()

    await waitFor(() => expect(screen.getByText('A')).toBeInTheDocument())
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('shows an honest empty state when nothing has been researched', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([])

    renderIt()

    expect(await screen.findByText(/will appear here once someone researches a stock/i)).toBeInTheDocument()
  })

  it('links each card to the stock page and the header to /research', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([entry()])

    renderIt()

    expect(await screen.findByRole('link', { name: /TCS/ })).toHaveAttribute('href', '/stock/TCS')
    expect(screen.getByRole('link', { name: 'View all' })).toHaveAttribute('href', '/research')
  })

  it('shows "Unavailable" score, never a fabricated number, when overall_score is null', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([entry({ overall_score: null })])

    renderIt()

    expect(await screen.findByText('—')).toBeInTheDocument()
  })
})
