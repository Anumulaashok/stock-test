import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { RiskSection } from './RiskSection'
import { buildReport } from '../test/fixtures'

describe('RiskSection', () => {
  it('places each indicator under its backend-reported severity bucket', () => {
    render(<RiskSection risk={buildReport().risk} />)
    expect(screen.getAllByText('High').length).toBeGreaterThan(0) // bucket heading + severity badge
    expect(screen.getAllByText('Informational').length).toBeGreaterThan(0) // bucket heading + badge
    expect(screen.getByText('High Debt To Equity')).toBeInTheDocument()
    expect(screen.getByText('Negative Fcf')).toBeInTheDocument()
  })

  it('shows the backend-provided reason, not a frontend-invented one', () => {
    render(<RiskSection risk={buildReport().risk} />)
    expect(screen.getByText('debt/equity is elevated')).toBeInTheDocument()
  })

  it('never shows Critical or Medium sections when empty', () => {
    render(<RiskSection risk={buildReport().risk} />)
    expect(screen.queryByText('Critical')).not.toBeInTheDocument()
    expect(screen.queryByText('Medium')).not.toBeInTheDocument()
  })

  it('handles missing risk section without crashing', () => {
    render(<RiskSection risk={null} />)
    expect(screen.getByText(/risk analysis is unavailable/i)).toBeInTheDocument()
  })
})
