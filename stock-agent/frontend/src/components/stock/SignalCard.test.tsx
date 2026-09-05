import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SignalCard, topPositiveAndWatch, scoreCoverage } from './SignalCard'
import { buildReport } from '../../test/fixtures'

describe('topPositiveAndWatch', () => {
  it('prefers the analyst strengths/weaknesses when the analyst ran', () => {
    const report = buildReport()
    expect(topPositiveAndWatch(report)).toEqual({ positive: 'Strong ROE', watch: 'High leverage' })
  })

  it('falls back to category reasons by band when the analyst did not run', () => {
    const report = buildReport({
      analyst: { source: 'analyst', available: false, investment_thesis: null, investment_thesis_evidence: null, strengths: [], weaknesses: [], category_analysis: [], key_takeaways: [], caveats: [] },
      scoring: {
        source: 'scoring',
        overall_score: '78',
        overall_status: 'calculated',
        band: 'good',
        categories: [
          { category: 'profitability', score: '85', weight: '0.20', status: 'calculated', band: 'strong', reason: 'ROE is strong', components: [] },
          { category: 'valuation', score: '40', weight: '0.20', status: 'calculated', band: 'weak', reason: 'Overvalued vs peers', components: [] },
        ],
      },
    })
    expect(topPositiveAndWatch(report)).toEqual({ positive: 'ROE is strong', watch: 'Overvalued vs peers' })
  })

  it('returns nulls when nothing is available from either source', () => {
    const report = buildReport({
      analyst: { source: 'analyst', available: false, investment_thesis: null, investment_thesis_evidence: null, strengths: [], weaknesses: [], category_analysis: [], key_takeaways: [], caveats: [] },
      scoring: null,
    })
    expect(topPositiveAndWatch(report)).toEqual({ positive: null, watch: null })
  })
})

describe('scoreCoverage', () => {
  it('counts categories with status calculated against the total', () => {
    expect(scoreCoverage(buildReport())).toEqual({ scored: 1, total: 2 })
  })

  it('returns null when there is no scoring section', () => {
    expect(scoreCoverage(buildReport({ scoring: null }))).toBeNull()
  })
})

describe('SignalCard', () => {
  it('renders the score, band, top positive/watch, coverage, and provider/freshness', () => {
    render(<SignalCard report={buildReport()} />)
    expect(screen.getByText('78')).toBeInTheDocument()
    expect(screen.getByText('Attractive')).toBeInTheDocument()
    expect(screen.getByText(/Strong ROE/)).toBeInTheDocument()
    expect(screen.getByText(/High leverage/)).toBeInTheDocument()
    expect(screen.getByText('1/2 inputs')).toBeInTheDocument()
    expect(screen.getByText(/yfinance/)).toBeInTheDocument()
    expect(screen.getByText(/live/)).toBeInTheDocument()
  })

  it('shows an em dash, never a fabricated 0, when the score is unavailable', () => {
    render(<SignalCard report={buildReport({ summary: { overall_score: null, overall_status: 'unavailable', score_band: null, signal: null, investment_thesis: null, key_takeaways: [] } })} />)
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('renders no provenance line when market is null', () => {
    render(<SignalCard report={buildReport({ market: null })} />)
    expect(screen.queryByText(/yfinance/)).not.toBeInTheDocument()
  })
})
