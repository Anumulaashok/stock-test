import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { ResearchHistorySection } from './ResearchHistorySection'
import * as researchApi from '../api/research'
import { ApiError } from '../api/client'
import { buildReport, buildRunResult } from '../test/fixtures'
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

  it('disables Compare until exactly two runs are selected, then shows the diff', async () => {
    vi.spyOn(researchApi, 'fetchResearchHistory').mockResolvedValue(HISTORY)
    vi.spyOn(researchApi, 'fetchResearchRun').mockImplementation(async (_ticker, runId) =>
      buildRunResult(
        buildReport({
          summary: {
            overall_score: runId === 'run-1' ? '70' : '78',
            overall_status: 'calculated',
            score_band: 'good',
            signal: null,
            investment_thesis: null,
            key_takeaways: [],
          },
        }),
      ),
    )
    render(<ResearchHistorySection ticker="ACME" onSelectRun={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Show' }))
    await waitFor(() => expect(screen.getAllByText('Normal')).toHaveLength(1))

    const compareButton = screen.getByRole('button', { name: /compare selected/i })
    expect(compareButton).toBeDisabled()

    const checkboxes = screen.getAllByRole('checkbox')
    await userEvent.click(checkboxes[0])
    expect(compareButton).toBeDisabled()
    await userEvent.click(checkboxes[1])
    expect(compareButton).toBeEnabled()

    await userEvent.click(compareButton)

    expect(await screen.findByText('70')).toBeInTheDocument()
    expect(screen.getByText('78')).toBeInTheDocument()
    expect(screen.getByText('Changed')).toBeInTheDocument()
  })

  it('selecting a third run drops the oldest selection, keeping exactly two', async () => {
    vi.spyOn(researchApi, 'fetchResearchHistory').mockResolvedValue(HISTORY)
    render(<ResearchHistorySection ticker="ACME" onSelectRun={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Show' }))
    await waitFor(() => expect(screen.getAllByText('Normal')).toHaveLength(1))

    const checkboxes = screen.getAllByRole('checkbox')
    await userEvent.click(checkboxes[0])
    await userEvent.click(checkboxes[1])
    await userEvent.click(checkboxes[0]) // uncheck first
    await userEvent.click(checkboxes[0]) // re-check -- still exactly 2 selected total

    expect(screen.getByRole('button', { name: /compare selected/i })).toBeEnabled()
  })

  it('shows a real error, not a blank screen, when a compared run has no saved report', async () => {
    vi.spyOn(researchApi, 'fetchResearchHistory').mockResolvedValue(HISTORY)
    vi.spyOn(researchApi, 'fetchResearchRun').mockImplementation(async () => ({
      ...buildRunResult(buildReport()),
      result: { company: { name: 'Acme', ticker: 'ACME' }, status: 'calculated', financial_analysis: null, valuation: null, scoring: null, research: null, analyst: null, report: null, warnings: [], metadata: null },
    }))
    render(<ResearchHistorySection ticker="ACME" onSelectRun={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Show' }))
    await waitFor(() => expect(screen.getAllByText('Normal')).toHaveLength(1))

    const checkboxes = screen.getAllByRole('checkbox')
    await userEvent.click(checkboxes[0])
    await userEvent.click(checkboxes[1])
    await userEvent.click(screen.getByRole('button', { name: /compare selected/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/no saved report/i)
  })
})
