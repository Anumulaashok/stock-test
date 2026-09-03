import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { RecentResearch } from './RecentResearch'
import { AuthProvider } from '../../auth/AuthContext'
import { setAuthToken } from '../../api/authToken'
import * as authApi from '../../api/auth'
import * as portfolioApi from '../../api/portfolio'
import * as researchApi from '../../api/research'
import { buildReport, buildRunResult } from '../../test/fixtures'
import type { UserPublic, WatchlistItem } from '../../types/backend'

afterEach(() => {
  vi.restoreAllMocks()
  setAuthToken(null)
})

function renderIt() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <RecentResearch />
      </AuthProvider>
    </MemoryRouter>,
  )
}

function user(overrides: Partial<UserPublic> = {}): UserPublic {
  return { id: 'u1', email: 'trader@example.com', created_at: '2026-01-01T00:00:00Z', ...overrides }
}

function watchlistItem(ticker: string): WatchlistItem {
  return { ticker, created_at: '2026-09-01T00:00:00Z' }
}

async function signIn() {
  setAuthToken('token-1')
  vi.spyOn(authApi, 'fetchCurrentUser').mockResolvedValue(user())
}

describe('RecentResearch', () => {
  it('prompts sign-in instead of fetching anything when anonymous', () => {
    const watchlistSpy = vi.spyOn(portfolioApi, 'fetchWatchlist')

    renderIt()

    expect(screen.getByText(/and research a stock to build your history here/)).toBeInTheDocument()
    expect(watchlistSpy).not.toHaveBeenCalled()
  })

  it('shows the honest placeholder for an empty watchlist, never a fake fan-out', async () => {
    await signIn()
    vi.spyOn(portfolioApi, 'fetchWatchlist').mockResolvedValue([])
    const researchSpy = vi.spyOn(researchApi, 'fetchLatestResearch')

    renderIt()

    expect(await screen.findByText("Research history will appear here once you've researched a stock.")).toBeInTheDocument()
    expect(researchSpy).not.toHaveBeenCalled()
  })

  it('fetches and shows research for a small watchlist', async () => {
    await signIn()
    vi.spyOn(portfolioApi, 'fetchWatchlist').mockResolvedValue([watchlistItem('TCS')])
    vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(
      buildRunResult(buildReport({ company: { name: 'Tata Consultancy Services', ticker: 'TCS', currency: null } }), {
        ticker: 'TCS',
      }),
    )

    renderIt()

    expect(await screen.findByText('TCS')).toBeInTheDocument()
    expect(screen.getByText('Tata Consultancy Services')).toBeInTheDocument()
  })

  it('links to research history instead of fanning out for a large watchlist', async () => {
    await signIn()
    vi.spyOn(portfolioApi, 'fetchWatchlist').mockResolvedValue(['A', 'B', 'C', 'D'].map(watchlistItem))
    const researchSpy = vi.spyOn(researchApi, 'fetchLatestResearch')

    renderIt()

    expect(await screen.findByRole('link', { name: /View research history/ })).toHaveAttribute('href', '/research')
    expect(researchSpy).not.toHaveBeenCalled()
  })
})
