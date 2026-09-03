import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { ResearchSnapshotBanner } from './ResearchSnapshotBanner'
import type { ResearchRunResult } from '../types/backend'

function runFixture(overrides: Partial<ResearchRunResult> = {}): ResearchRunResult {
  return {
    research_run_id: 'run-1',
    ticker: 'ACME',
    research_date: '2026-09-02',
    run_type: 'NORMAL',
    status: 'COMPLETED',
    is_new_run: true,
    started_at: '2026-09-02T10:00:00Z',
    completed_at: '2026-09-02T10:32:00Z',
    result: {
      company: { name: 'Acme Corp', ticker: 'ACME' }, status: 'calculated',
      financial_analysis: null, valuation: null, scoring: null, research: null, analyst: null,
      report: null, warnings: [], metadata: null,
    },
    ...overrides,
  }
}

describe('ResearchSnapshotBanner', () => {
  it('shows the snapshot timestamp', () => {
    render(<ResearchSnapshotBanner run={runFixture()} refreshing={false} onRefresh={vi.fn()} onForceRefresh={vi.fn()} />)
    expect(screen.getByText('Research Snapshot')).toBeInTheDocument()
    expect(screen.getByText(/2026/)).toBeInTheDocument()
  })

  it('indicates when a saved snapshot was reused rather than freshly computed', () => {
    render(<ResearchSnapshotBanner run={runFixture({ is_new_run: false })} refreshing={false} onRefresh={vi.fn()} onForceRefresh={vi.fn()} />)
    expect(screen.getByText(/reused from a saved snapshot/i)).toBeInTheDocument()
  })

  it('does not claim reuse for a freshly computed run', () => {
    render(<ResearchSnapshotBanner run={runFixture({ is_new_run: true })} refreshing={false} onRefresh={vi.fn()} onForceRefresh={vi.fn()} />)
    expect(screen.queryByText(/reused from a saved snapshot/i)).not.toBeInTheDocument()
  })

  it('calls onRefresh and onForceRefresh from their respective buttons', async () => {
    const onRefresh = vi.fn()
    const onForceRefresh = vi.fn()
    render(<ResearchSnapshotBanner run={runFixture()} refreshing={false} onRefresh={onRefresh} onForceRefresh={onForceRefresh} />)

    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    expect(onRefresh).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('button', { name: /force refresh/i }))
    expect(onForceRefresh).toHaveBeenCalledTimes(1)
  })

  it('disables both buttons while refreshing', () => {
    render(<ResearchSnapshotBanner run={runFixture()} refreshing={true} onRefresh={vi.fn()} onForceRefresh={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeDisabled()
    expect(screen.getByRole('button', { name: /refreshing/i })).toBeDisabled()
  })
})
