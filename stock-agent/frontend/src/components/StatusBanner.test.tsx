import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { StatusBanner } from './StatusBanner'

describe('StatusBanner', () => {
  it('renders nothing for a fully calculated result', () => {
    const { container } = render(<StatusBanner status="calculated" ticker="ACME" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows a partial banner without implying total failure', () => {
    render(<StatusBanner status="partial" ticker="ACME" />)
    expect(screen.getByText('Analysis partially completed')).toBeInTheDocument()
    expect(screen.queryByText('Analysis failed')).not.toBeInTheDocument()
  })

  it('shows a failed banner for failed status', () => {
    render(<StatusBanner status="failed" ticker="ACME" />)
    expect(screen.getByText('Analysis failed')).toBeInTheDocument()
  })
})
