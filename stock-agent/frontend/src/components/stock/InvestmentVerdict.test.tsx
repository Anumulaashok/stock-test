import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { InvestmentVerdict } from './InvestmentVerdict'
import type { ReportSummary } from '../../types/backend'

function buildSummary(overrides: Partial<ReportSummary> = {}): ReportSummary {
  return {
    overall_score: '70',
    overall_status: 'calculated',
    score_band: 'strong',
    signal: null,
    investment_thesis: null,
    key_takeaways: [],
    ...overrides,
  }
}

describe('InvestmentVerdict', () => {
  it('eventually shows the real score (count-up settles on the true value)', async () => {
    render(<InvestmentVerdict summary={buildSummary({ overall_score: '70' })} />)
    await waitFor(() => expect(screen.getByText('70')).toBeInTheDocument(), { timeout: 5000 })
    expect(screen.getByText('/100')).toBeInTheDocument()
  })

  it('shows the band label alongside the score', async () => {
    render(<InvestmentVerdict summary={buildSummary({ score_band: 'strong' })} />)
    await waitFor(() => expect(screen.getByText('70')).toBeInTheDocument(), { timeout: 5000 })
    expect(screen.getByText('Attractive')).toBeInTheDocument()
  })

  it('shows "Score unavailable" rather than animating toward a fabricated number when there is none', () => {
    render(<InvestmentVerdict summary={buildSummary({ overall_score: null, score_band: null })} />)
    expect(screen.getByText('Score unavailable')).toBeInTheDocument()
  })
})
