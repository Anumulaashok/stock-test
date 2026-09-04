import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { HomePage } from './HomePage'
import { AuthProvider } from '../auth/AuthContext'
import * as marketHistoryApi from '../api/marketHistory'
import * as sectorsApi from '../api/sectors'
import * as researchApi from '../api/research'

afterEach(() => vi.restoreAllMocks())

describe('HomePage', () => {
  it('renders for an anonymous visitor without crashing', async () => {
    vi.spyOn(marketHistoryApi, 'fetchIndexQuotes').mockResolvedValue({ indices: [] })
    vi.spyOn(sectorsApi, 'fetchMarketOpportunity').mockResolvedValue({
      status: 'success',
      generated_at: '2026-09-04T00:00:00Z',
      sectors: [],
      warnings: [],
    })
    // Research is global (no user_id), so RecentResearch renders for
    // everyone -- only WatchlistSummary is auth-gated.
    vi.spyOn(researchApi, 'fetchRecentResearch').mockResolvedValue([])

    render(
      <MemoryRouter>
        <AuthProvider>
          <HomePage />
        </AuthProvider>
      </MemoryRouter>,
    )

    expect(screen.getByText('Market Snapshot')).toBeInTheDocument()
    expect(screen.getByText('Top Opportunities')).toBeInTheDocument()
    expect(screen.getByText('Recent Research')).toBeInTheDocument()
    expect(screen.getByText('Watchlist')).toBeInTheDocument()
    // WatchlistSummary renders an anonymous "Sign in" prompt.
    expect(await screen.findByText(/Sign in/)).toBeInTheDocument()
  })
})
