import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { WarningsSection } from './WarningsSection'
import { buildReport } from '../test/fixtures'

describe('WarningsSection', () => {
  it('renders every warning with its source, never hiding them', () => {
    render(<WarningsSection warnings={buildReport().warnings} />)
    expect(screen.getByText('Only two fiscal periods of data are available.')).toBeInTheDocument()
    expect(screen.getByText('target EV/EBITDA multiple is missing')).toBeInTheDocument()
    expect(screen.getByText('Financial Analysis')).toBeInTheDocument()
    expect(screen.getByText('Valuation')).toBeInTheDocument()
  })

  it('renders nothing when there are no warnings', () => {
    const { container } = render(<WarningsSection warnings={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
