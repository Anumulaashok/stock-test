import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { LoadingState } from './LoadingState'

describe('LoadingState', () => {
  it('shows an honest, non-staged loading message naming the ticker', () => {
    render(<LoadingState ticker="ACME" />)
    expect(screen.getByText('Analyzing ACME…')).toBeInTheDocument()
  })

  it('never fabricates completed stage checkmarks', () => {
    render(<LoadingState ticker="ACME" />)
    expect(screen.queryByText(/✓/)).not.toBeInTheDocument()
  })

  it('is announced to assistive technology via a status role', () => {
    render(<LoadingState ticker="ACME" />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})
