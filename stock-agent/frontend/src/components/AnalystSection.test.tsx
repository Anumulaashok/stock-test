import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { AnalystSection } from './AnalystSection'
import { buildReport } from '../test/fixtures'

describe('AnalystSection', () => {
  it('renders thesis, strengths, weaknesses, takeaways, and caveats', () => {
    render(<AnalystSection analyst={buildReport().analyst} />)
    expect(screen.getByText('Acme Corp shows strong profitability.')).toBeInTheDocument()
    expect(screen.getByText('Strong ROE')).toBeInTheDocument()
    expect(screen.getByText('High leverage')).toBeInTheDocument()
    expect(screen.getByText('Limited periods available')).toBeInTheDocument()
  })

  it('reveals evidence references on demand, sourced from the backend', async () => {
    render(<AnalystSection analyst={buildReport().analyst} />)
    const toggle = screen.getAllByRole('button', { name: /why does the ai say this/i })[0]
    await userEvent.click(toggle)
    expect(screen.getByText('Roe')).toBeInTheDocument()
  })

  it('never contains a buy/sell/hold recommendation', () => {
    render(<AnalystSection analyst={buildReport().analyst} />)
    const text = document.body.textContent?.toLowerCase() ?? ''
    expect(text).not.toContain('buy')
    expect(text).not.toContain('sell')
    expect(text).not.toMatch(/\bhold\b/)
  })

  it('shows an unavailable message when the analyst did not run, without hiding the rest of the page', () => {
    render(<AnalystSection analyst={{ source: 'analyst', available: false, investment_thesis: null, investment_thesis_evidence: null, strengths: [], weaknesses: [], category_analysis: [], key_takeaways: [], caveats: [] }} />)
    expect(screen.getByText(/ai analyst commentary is unavailable/i)).toBeInTheDocument()
  })
})
