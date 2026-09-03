import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { ResearchHistorySection } from './ResearchHistorySection'
import * as researchApi from '../api/research'
import { ApiError } from '../api/client'
import type { ResearchRunSummary } from '../types/backend'

const HISTORY: ResearchRunSummary[] = [
  {
    id: 'run-2', ticker: 'ACME', research_date: '2026-09-02', run_type: 'FORCE_REFRESH', status: 'COMPLETED',
    started_at: '2026-09-02T18:15:00Z', completed_at: '2026-09-02T18:15:05Z', error_message: null,
  },
  {
    id: 'run-1', ticker: 'ACME', research_date: '2026-09-02', run_type: 'NORMAL', status: 'COMPLETED',
    started_at: '2026-09-02T10:32:00Z', completed_at: '2026-09-02T10:32:05Z', error_message: null,
  },
]

describe('ResearchHistorySection', () => {
  it('is collapsed by default and does not fetch history until shown', () => {
    const fetchSpy = vi.spyOn(researchApi, 'fetchResearchHistory')
    render(<ResearchHistorySection ticker="ACME" onSelectRun={vi.fn()} />)
    expect(screen.queryByText('run-1')).not.toBeInTheDocument()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('fetches and shows history rows when opened', async () => {
    vi.spyOn(researchApi, 'fetchResearchHistory').mockResolvedValue(HISTORY)
    render(<ResearchHistorySection ticker="ACME" onSelectRun={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Show' }))

    await waitFor(() => expect(screen.getAllByText('Force Refresh')).toHaveLength(1))
    expect(screen.getAllByText('Normal')).toHaveLength(1)
    expect(screen.getAllByText('COMPLETED')).toHaveLength(2)
  })

  it('calls onSelectRun with the clicked run id, and never re-fetches history for it', async () => {
    vi.spyOn(researchApi, 'fetchResearchHistory').mockResolvedValue(HISTORY)
    const onSelectRun = vi.fn()
    render(<ResearchHistorySection ticker="ACME" onSelectRun={onSelectRun} />)

    await userEvent.click(screen.getByRole('button', { name: 'Show' }))
    await waitFor(() => expect(screen.getAllByText('Normal')).toHaveLength(1))

    await userEvent.click(screen.getByText('Normal').closest('tr')!.querySelector('button')!)
    expect(onSelectRun).toHaveBeenCalledWith('run-1')
  })

  it('shows an empty state when there is no history yet', async () => {
    vi.spyOn(researchApi, 'fetchResearchHistory').mockResolvedValue([])
    render(<ResearchHistorySection ticker="ACME" onSelectRun={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Show' }))
    await waitFor(() => expect(screen.getByText(/no past research for acme/i)).toBeInTheDocument())
  })

  it('surfaces a real error message rather than failing silently', async () => {
    vi.spyOn(researchApi, 'fetchResearchHistory').mockRejectedValue(new ApiError('Could not reach the server.', 'network'))
    render(<ResearchHistorySection ticker="ACME" onSelectRun={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Show' }))
    await waitFor(() => expect(screen.getByText('Could not reach the server.')).toBeInTheDocument())
  })
})
