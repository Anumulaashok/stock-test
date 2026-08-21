import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ValuationSection } from './ValuationSection'
import { buildReport } from '../test/fixtures'

describe('ValuationSection', () => {
  it('renders every valuation method independently, never averaged', () => {
    render(<ValuationSection valuation={buildReport().valuation} />)
    expect(screen.getByText('DCF')).toBeInTheDocument()
    expect(screen.getByText('P/E')).toBeInTheDocument()
    expect(screen.getByText('$140.00')).toBeInTheDocument()
    // The backend explicitly never averages/blends methods -- the UI must
    // not invent a composite figure or pick a "winning" method either.
    expect(screen.queryByText(/average (value|intrinsic)/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/composite/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/best valuation/i)).not.toBeInTheDocument()
  })

  it('renders an unavailable method as "Unavailable", never as $0', () => {
    render(<ValuationSection valuation={buildReport().valuation} />)
    expect(screen.getByText('EPS is missing')).toBeInTheDocument()
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument()
  })

  it('shows upside/downside from the backend', () => {
    render(<ValuationSection valuation={buildReport().valuation} />)
    expect(screen.getByText(/40\.00% vs\. current price/)).toBeInTheDocument()
  })

  it('handles missing valuation section without crashing', () => {
    render(<ValuationSection valuation={null} />)
    expect(screen.getByText(/valuation is unavailable/i)).toBeInTheDocument()
  })
})
