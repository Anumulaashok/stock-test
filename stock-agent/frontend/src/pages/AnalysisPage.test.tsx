import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { AnalysisPage } from './AnalysisPage'
import { AuthProvider } from '../auth/AuthContext'
import { buildReport } from '../test/fixtures'
import * as researchApi from '../api/research'
import * as searchApi from '../api/search'
import { ApiError } from '../api/client'
import type { CombinedAnalysisResult, ResearchRunResult } from '../types/backend'

function renderPage(props?: Parameters<typeof AnalysisPage>[0]) {
  return render(
    <AuthProvider>
      <AnalysisPage {...props} />
    </AuthProvider>,
  )
}

async function search(ticker: string) {
  await userEvent.type(screen.getByLabelText(/ticker symbol/i), ticker)
  await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
}

function runResult(result: CombinedAnalysisResult, overrides: Partial<ResearchRunResult> = {}): ResearchRunResult {
  return {
    research_run_id: 'run-1',
    ticker: 'ACME',
    research_date: '2026-09-02',
    run_type: 'NORMAL',
    status: 'COMPLETED',
    is_new_run: true,
    started_at: '2026-09-02T10:00:00Z',
    completed_at: '2026-09-02T10:00:05Z',
    result,
    ...overrides,
  }
}

describe('AnalysisPage', () => {
  beforeEach(() => {
    // The search bar's own autocomplete suggestions are covered by
    // SearchBar.test.tsx -- keep them out of the way here.
    vi.spyOn(searchApi, 'searchStocks').mockResolvedValue([])
    // A plain search checks for an already-computed latest result first;
    // default to "nothing yet" so these tests fall through to
    // `runResearch` exactly as before, unless a test overrides this.
    vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(null)
  })


  it('shows a loading state, then the successful result', async () => {
    const result: CombinedAnalysisResult = {
      company: { name: 'Acme Corp', ticker: 'ACME' },
      status: 'calculated',
      financial_analysis: null, valuation: null, scoring: null, research: null, analyst: null,
      report: buildReport(),
      warnings: [],
      metadata: { pipeline_version: '1.0', started_at: '', completed_at: '', duration_ms: 1 },
    }
    let resolveAnalysis!: (value: ResearchRunResult) => void
    const pending = new Promise<ResearchRunResult>((resolve) => {
      resolveAnalysis = resolve
    })
    vi.spyOn(researchApi, 'runResearch').mockReturnValue(pending)

    renderPage()
    await search('ACME')

    expect(await screen.findByText(/analyzing ACME/i)).toBeInTheDocument()

    resolveAnalysis(runResult(result))

    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: /acme corp/i })).toBeInTheDocument())
    expect(screen.queryByText(/analyzing ACME/i)).not.toBeInTheDocument()
    // the research snapshot banner is shown, distinguishing this from live data
    expect(screen.getByText('Research Snapshot')).toBeInTheDocument()
  })

  it('renders a partial result with deterministic sections intact', async () => {
    const partialReport = buildReport({
      status: 'partial',
      analyst: { source: 'analyst', available: false, investment_thesis: null, investment_thesis_evidence: null, strengths: [], weaknesses: [], category_analysis: [], key_takeaways: [], caveats: [] },
      warnings: [{ source: 'analyst', code: 'timeout', message: 'Local LLM request timed out' }],
    })
    const result: CombinedAnalysisResult = {
      company: { name: 'Acme Corp', ticker: 'ACME' },
      status: 'partial',
      financial_analysis: null, valuation: null, scoring: null, research: null, analyst: null,
      report: partialReport,
      warnings: [],
      metadata: { pipeline_version: '1.0', started_at: '', completed_at: '', duration_ms: 1 },
    }
    vi.spyOn(researchApi, 'runResearch').mockResolvedValue(runResult(result, { status: 'PARTIAL' }))

    renderPage()
    await search('ACME')

    await waitFor(() => expect(screen.getByText('Analysis partially completed')).toBeInTheDocument())
    // Deterministic sections are still shown, not hidden behind a failure page.
    expect(screen.getAllByText('Profitability').length).toBeGreaterThan(0)
    expect(screen.getByText('DCF')).toBeInTheDocument()
    expect(screen.getByText(/ai analyst commentary is unavailable/i)).toBeInTheDocument()
  })

  it('renders a failed report status without hiding the reported warnings', async () => {
    const failedReport = buildReport({
      status: 'failed',
      financials: null, valuation: null, scoring: null, risk: null, research: null,
      analyst: { source: 'analyst', available: false, investment_thesis: null, investment_thesis_evidence: null, strengths: [], weaknesses: [], category_analysis: [], key_takeaways: [], caveats: [] },
      warnings: [{ source: 'pipeline', code: null, message: 'Pipeline failed during the financial_analysis stage.' }],
    })
    const result: CombinedAnalysisResult = {
      company: { name: 'Acme Corp', ticker: 'ACME' },
      status: 'failed',
      financial_analysis: null, valuation: null, scoring: null, research: null, analyst: null,
      report: failedReport,
      warnings: [],
      metadata: { pipeline_version: '1.0', started_at: '', completed_at: '', duration_ms: 1 },
    }
    vi.spyOn(researchApi, 'runResearch').mockResolvedValue(runResult(result, { status: 'FAILED' }))

    renderPage()
    await search('ACME')

    await waitFor(() => expect(screen.getByText('Analysis failed')).toBeInTheDocument())
    expect(screen.getByText('Pipeline failed during the financial_analysis stage.')).toBeInTheDocument()
  })

  it('renders a friendly error banner on a transport-level failure, never a raw exception', async () => {
    vi.spyOn(researchApi, 'runResearch').mockRejectedValue(new ApiError('Could not reach the analysis server. Check your connection.', 'network'))

    renderPage()
    await search('ACME')

    await waitFor(() => expect(screen.getByText('Could not complete analysis')).toBeInTheDocument())
    expect(screen.queryByText(/traceback/i)).not.toBeInTheDocument()
  })

  it('shows the already-latest computed result on search without triggering a new run', async () => {
    const result: CombinedAnalysisResult = {
      company: { name: 'Acme Corp', ticker: 'ACME' },
      status: 'calculated',
      financial_analysis: null, valuation: null, scoring: null, research: null, analyst: null,
      report: buildReport(),
      warnings: [],
      metadata: { pipeline_version: '1.0', started_at: '', completed_at: '', duration_ms: 1 },
    }
    const latest = runResult(result, { is_new_run: false, run_type: 'FORCE_REFRESH' })
    vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(latest)
    const runResearchSpy = vi.spyOn(researchApi, 'runResearch')
    const callsBefore = runResearchSpy.mock.calls.length

    renderPage()
    await search('ACME')

    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: /acme corp/i })).toBeInTheDocument())
    expect(runResearchSpy.mock.calls.length).toBe(callsBefore)
  })
})
