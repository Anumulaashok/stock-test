import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ScoreOverview } from './ScoreOverview'
import { buildReport } from '../test/fixtures'

describe('ScoreOverview', () => {
  it('renders a calculated category score', () => {
    render(<ScoreOverview scoring={buildReport().scoring} />)
    expect(screen.getByText('Profitability')).toBeInTheDocument()
    expect(screen.getByText('85.0')).toBeInTheDocument()
    expect(screen.getByText('strong')).toBeInTheDocument()
  })

  it('renders an unavailable category as "Unavailable", never as 0', () => {
    render(<ScoreOverview scoring={buildReport().scoring} />)
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0)
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('shows the unavailable reason from the backend', () => {
    render(<ScoreOverview scoring={buildReport().scoring} />)
    expect(screen.getByText('No valuation data was provided.')).toBeInTheDocument()
  })

  it('handles a missing scoring section without crashing', () => {
    render(<ScoreOverview scoring={null} />)
    expect(screen.getByText(/scoring is unavailable/i)).toBeInTheDocument()
  })
})
