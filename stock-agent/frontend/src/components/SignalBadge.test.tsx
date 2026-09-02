import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { SignalBadge } from './SignalBadge'
import type { ReportSignal } from '../types/backend'

describe('SignalBadge', () => {
  it('renders nothing when signal is null', () => {
    const { container } = render(<SignalBadge signal={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the label and reason for a strong (green) signal', () => {
    const signal: ReportSignal = { label: 'strong', color: 'green', reason: 'Overall score is good.' }
    render(<SignalBadge signal={signal} />)
    expect(screen.getByText('Strong')).toBeInTheDocument()
    expect(screen.getByText('Overall score is good.')).toBeInTheDocument()
  })

  it('renders a moderate (yellow) signal', () => {
    const signal: ReportSignal = { label: 'moderate', color: 'yellow', reason: 'A high-severity risk was flagged.' }
    render(<SignalBadge signal={signal} />)
    expect(screen.getByText('Moderate')).toBeInTheDocument()
  })

  it('renders a weak (red) signal', () => {
    const signal: ReportSignal = { label: 'weak', color: 'red', reason: 'Overall score is weak.' }
    render(<SignalBadge signal={signal} />)
    expect(screen.getByText('Weak')).toBeInTheDocument()
  })

  it('renders an unavailable (gray) signal', () => {
    const signal: ReportSignal = { label: 'unavailable', color: 'gray', reason: 'Not enough data.' }
    render(<SignalBadge signal={signal} />)
    expect(screen.getByText('Unavailable')).toBeInTheDocument()
  })
})
