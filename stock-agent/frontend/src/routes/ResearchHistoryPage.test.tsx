import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { ResearchHistoryPage } from './ResearchHistoryPage'
import * as researchApi from '../api/research'
import type { RecentResearchEntry } from '../types/backend'

afterEach(() => {
  vi.restoreAllMocks()
})

function renderIt() {
  return render(
    <MemoryRouter>
      <ResearchHistoryPage />
    </MemoryRouter>,
  )
}

function entry(overrides: Partial<RecentResearchEntry> = {}): RecentResearchEntry {
  return {
    ticker: 'HUDCO',
    company_name: 'Housing & Urban Development Corp',
    research_run_id: 'run-1',
    research_date: '2026-09-02',
    status: 'COMPLETED',
    run_type: 'NORMAL',
    overall_score: '81',
    band: 'strong',
    completed_at: '2026-09-02T10:00:00Z',
    ...overrides,
  }
}

describe('ResearchHistoryPage', () => {
  it('renders every entry as a link to its stock page', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([entry(), entry({ ticker: 'TCS', research_run_id: 'run-2' })])

    renderIt()

    expect(await screen.findByRole('link', { name: /HUDCO/ })).toHaveAttribute('href', '/stock/HUDCO')
    expect(screen.getByRole('link', { name: /TCS/ })).toHaveAttribute('href', '/stock/TCS')
  })

  it('shows an honest empty state, not a fabricated list, when nothing has been researched', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([])

    renderIt()

    expect(await screen.findByText(/nothing has been researched yet/i)).toBeInTheDocument()
  })

  it('is not scoped to any user -- no "your research" language', async () => {
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([entry()])

    renderIt()

    await screen.findByText('HUDCO')
    expect(screen.queryByText(/your research/i)).not.toBeInTheDocument()
  })
})
