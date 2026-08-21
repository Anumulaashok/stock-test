import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { AnalysisPage } from './AnalysisPage'
import { buildReport } from '../test/fixtures'
import * as analysisApi from '../api/analysis'
import { ApiError } from '../api/client'
import type { CombinedAnalysisResult } from '../types/backend'

async function search(ticker: string) {
  await userEvent.type(screen.getByLabelText(/ticker symbol/i), ticker)
  await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
}

describe('AnalysisPage', () => {
  it('shows a loading state, then the successful result', async () => {
    const result: CombinedAnalysisResult = {
      company: { name: 'Acme Corp', ticker: 'ACME' },
      status: 'calculated',
      financial_analysis: null, valuation: null, scoring: null, research: null, analyst: null,
      report: buildReport(),
      warnings: [],
      metadata: { pipeline_version: '1.0', started_at: '', completed_at: '', duration_ms: 1 },
    }
    let resolveAnalysis!: (value: CombinedAnalysisResult) => void
    const pending = new Promise<CombinedAnalysisResult>((resolve) => {
      resolveAnalysis = resolve
    })
    vi.spyOn(analysisApi, 'analyzeTicker').mockReturnValue(pending)

    render(<AnalysisPage />)
    await search('ACME')

    expect(await screen.findByText(/analyzing ACME/i)).toBeInTheDocument()

    resolveAnalysis(result)

    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: /acme corp/i })).toBeInTheDocument())
    expect(screen.queryByText(/analyzing ACME/i)).not.toBeInTheDocument()
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
    vi.spyOn(analysisApi, 'analyzeTicker').mockResolvedValue(result)

    render(<AnalysisPage />)
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
    vi.spyOn(analysisApi, 'analyzeTicker').mockResolvedValue(result)

    render(<AnalysisPage />)
    await search('ACME')

    await waitFor(() => expect(screen.getByText('Analysis failed')).toBeInTheDocument())
    expect(screen.getByText('Pipeline failed during the financial_analysis stage.')).toBeInTheDocument()
  })

  it('renders a friendly error banner on a transport-level failure, never a raw exception', async () => {
    vi.spyOn(analysisApi, 'analyzeTicker').mockRejectedValue(new ApiError('Could not reach the analysis server. Check your connection.', 'network'))

    render(<AnalysisPage />)
    await search('ACME')

    await waitFor(() => expect(screen.getByText('Could not complete analysis')).toBeInTheDocument())
    expect(screen.queryByText(/traceback/i)).not.toBeInTheDocument()
  })
})
