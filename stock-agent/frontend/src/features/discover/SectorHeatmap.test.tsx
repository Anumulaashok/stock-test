import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SectorHeatmap } from './SectorHeatmap'
import type { SectorSummary } from '../../types/backend'

function buildSector(overrides: Partial<SectorSummary> = {}): SectorSummary {
  return {
    sector: 'Technology',
    sector_score: '82',
    outlook: 'bullish',
    risk: 'low',
    growth_score: '75',
    valuation_score: '60',
    momentum_score: '70',
    news_headline_count: 3,
    constituents_evaluated: 8,
    constituents_total: 10,
    top_stocks: [],
    ...overrides,
  }
}

describe('SectorHeatmap', () => {
  it('renders one tile per sector with its real score visible, not color alone', () => {
    render(
      <SectorHeatmap
        sectors={[buildSector({ sector: 'Technology', sector_score: '82' }), buildSector({ sector: 'Energy', sector_score: '30' })]}
        selectedSector="Technology"
        onSelect={vi.fn()}
      />,
    )
    expect(screen.getByText('Technology')).toBeInTheDocument()
    expect(screen.getByText('82')).toBeInTheDocument()
    expect(screen.getByText('Energy')).toBeInTheDocument()
    expect(screen.getByText('30')).toBeInTheDocument()
  })

  it('shows "Unavailable" rather than a fabricated score for a null sector_score', () => {
    render(<SectorHeatmap sectors={[buildSector({ sector_score: null })]} selectedSector="Technology" onSelect={vi.fn()} />)
    expect(screen.getByRole('gridcell', { name: /unavailable/i })).toBeInTheDocument()
  })

  it('renders a legend spelling out what each color means', () => {
    render(<SectorHeatmap sectors={[buildSector()]} selectedSector="Technology" onSelect={vi.fn()} />)
    expect(screen.getByText(/strong \(70\+\)/i)).toBeInTheDocument()
    expect(screen.getByText(/weak \(<45\)/i)).toBeInTheDocument()
  })

  it('calls onSelect when a tile is clicked', async () => {
    const onSelect = vi.fn()
    render(
      <SectorHeatmap
        sectors={[buildSector({ sector: 'Technology' }), buildSector({ sector: 'Energy' })]}
        selectedSector="Technology"
        onSelect={onSelect}
      />,
    )
    await userEvent.click(screen.getByRole('gridcell', { name: /energy/i }))
    expect(onSelect).toHaveBeenCalledWith('Energy')
  })

  it('moves focus to the next tile on ArrowRight (keyboard traversal)', async () => {
    render(
      <SectorHeatmap
        sectors={[buildSector({ sector: 'Technology' }), buildSector({ sector: 'Energy' })]}
        selectedSector="Technology"
        onSelect={vi.fn()}
      />,
    )
    const first = screen.getByRole('gridcell', { name: /technology/i })
    first.focus()
    await userEvent.keyboard('{ArrowRight}')

    expect(screen.getByRole('gridcell', { name: /energy/i })).toHaveFocus()
  })

  it('only the currently-focused tile is in the tab order (roving tabindex)', () => {
    render(
      <SectorHeatmap
        sectors={[buildSector({ sector: 'Technology' }), buildSector({ sector: 'Energy' })]}
        selectedSector="Technology"
        onSelect={vi.fn()}
      />,
    )
    expect(screen.getByRole('gridcell', { name: /technology/i })).toHaveAttribute('tabIndex', '0')
    expect(screen.getByRole('gridcell', { name: /energy/i })).toHaveAttribute('tabIndex', '-1')
  })
})
