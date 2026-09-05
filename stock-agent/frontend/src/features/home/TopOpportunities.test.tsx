import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { TopOpportunities } from './TopOpportunities'
import * as sectorsApi from '../../api/sectors'
import type { MarketOpportunityResult, SectorSummary } from '../../types/backend'

afterEach(() => vi.restoreAllMocks())

function sector(overrides: Partial<SectorSummary> = {}): SectorSummary {
  return {
    sector: 'Information Technology',
    sector_score: '82',
    outlook: 'bullish',
    risk: 'low',
    growth_score: '80',
    valuation_score: '75',
    momentum_score: '85',
    news_headline_count: 4,
    constituents_evaluated: 10,
    constituents_total: 10,
    top_stocks: [
      { ticker: 'TCS', company_name: 'Tata Consultancy Services', overall_score: '88', band: 'strong', status: 'calculated' },
    ],
    ...overrides,
  }
}

function result(overrides: Partial<MarketOpportunityResult> = {}): MarketOpportunityResult {
  return { status: 'success', generated_at: '2026-09-04T00:00:00Z', sectors: [sector()], warnings: [], ...overrides }
}

function renderIt() {
  return render(
    <MemoryRouter>
      <TopOpportunities />
    </MemoryRouter>,
  )
}

describe('TopOpportunities', () => {
  it('renders ranked sectors and their top stocks', async () => {
    vi.spyOn(sectorsApi, 'fetchMarketOpportunity').mockResolvedValue(result())

    renderIt()

    expect(await screen.findByText('Information Technology')).toBeInTheDocument()
    expect(screen.getByText('TCS')).toBeInTheDocument()
    expect(screen.getByText('Score 82')).toBeInTheDocument()
  })

  it('calls out elevated-risk sectors without inventing a stock-level alert', async () => {
    vi.spyOn(sectorsApi, 'fetchMarketOpportunity').mockResolvedValue(
      result({ sectors: [sector({ sector: 'Energy', risk: 'high' })] }),
    )

    renderIt()

    expect(await screen.findByText(/Elevated-risk sectors right now: Energy/)).toBeInTheDocument()
  })

  it('does not show a risk callout when nothing is elevated', async () => {
    vi.spyOn(sectorsApi, 'fetchMarketOpportunity').mockResolvedValue(result())

    renderIt()

    await screen.findByText('Information Technology')
    expect(screen.queryByText(/Elevated-risk sectors/)).not.toBeInTheDocument()
  })

  it('shows an honest unavailable message rather than an empty page', async () => {
    vi.spyOn(sectorsApi, 'fetchMarketOpportunity').mockResolvedValue(result({ status: 'unavailable', sectors: [] }))

    renderIt()

    expect(await screen.findByText('Sector ranking is unavailable right now.')).toBeInTheDocument()
  })
})
