import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RiskOverview } from './RiskOverview'
import { buildReport } from '../../test/fixtures'

describe('RiskOverview', () => {
  it('shows a qualitative headline built from real severity counts, not a fabricated score', () => {
    const report = buildReport()
    render(<RiskOverview risk={report.risk} />)
    expect(screen.getByText('High Risk')).toBeInTheDocument()
    expect(screen.getByText('1 high')).toBeInTheDocument()
    expect(screen.queryByText(/\/\s*100/)).not.toBeInTheDocument()
  })

  it('renders an explicit unavailable state when risk analysis did not run', () => {
    const report = buildReport({ risk: null })
    render(<RiskOverview risk={report.risk} />)
    expect(screen.getByText('Risk analysis unavailable')).toBeInTheDocument()
  })
})
