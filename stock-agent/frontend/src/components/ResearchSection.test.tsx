import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ResearchSection } from './ResearchSection'
import { buildReport } from '../test/fixtures'

describe('ResearchSection', () => {
  it('renders research items with attribution', () => {
    render(<ResearchSection research={buildReport().research} />)
    expect(screen.getByText('Acme Corp expands into new market')).toBeInTheDocument()
    expect(screen.getByText('Example News')).toBeInTheDocument()
    expect(screen.getByText('research_001')).toBeInTheDocument()
  })

  it('shows freshness as reported, never converting unknown to recent', () => {
    render(<ResearchSection research={buildReport().research} />)
    expect(screen.getByText('Recent')).toBeInTheDocument()
    expect(screen.getByText('Unknown date')).toBeInTheDocument()
  })

  it('renders a safe http(s) URL as a clickable link', () => {
    render(<ResearchSection research={buildReport().research} />)
    const link = screen.getByRole('link', { name: /source/i })
    expect(link).toHaveAttribute('href', 'https://example.com/a')
  })

  it('never renders a javascript: URL as a clickable link', () => {
    render(<ResearchSection research={buildReport().research} />)
    const links = screen.getAllByRole('link')
    for (const link of links) {
      expect(link.getAttribute('href')).not.toMatch(/^javascript:/i)
    }
    expect(screen.getByText('Source unavailable')).toBeInTheDocument()
  })

  it('handles research unavailable without crashing', () => {
    render(<ResearchSection research={{ source: 'research', available: false, items: [] }} />)
    expect(screen.getByText(/no research context is available/i)).toBeInTheDocument()
  })
})
