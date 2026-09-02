import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { DataQualitySection } from './DataQualitySection'
import { buildReport } from '../test/fixtures'

describe('DataQualitySection', () => {
  it('derives a metric count from the real per-metric statuses, never a fabricated percentage', () => {
    render(<DataQualitySection report={buildReport()} />)
    // fixture: financials 1 calculated (roe) + 1 unavailable (fcf_growth);
    // valuation 1 calculated (dcf) + 1 unavailable (pe); risk 2 calculated
    // (high_debt_to_equity, negative_fcf) => 4 of 6
    expect(screen.getByText(/4 of 6 metrics evaluated/)).toBeInTheDocument()
    expect(screen.getByText(/2 unavailable/)).toBeInTheDocument()
  })

  it('renders nothing when there is no evaluable data at all', () => {
    const { container } = render(
      <DataQualitySection report={buildReport({ financials: null, valuation: null, risk: null })} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
