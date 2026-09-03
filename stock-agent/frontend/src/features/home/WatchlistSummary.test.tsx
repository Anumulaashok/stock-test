import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { WatchlistSummary } from './WatchlistSummary'
import { AuthProvider } from '../../auth/AuthContext'
import { setAuthToken } from '../../api/authToken'
import * as authApi from '../../api/auth'
import * as portfolioApi from '../../api/portfolio'
import type { UserPublic } from '../../types/backend'

afterEach(() => {
  vi.restoreAllMocks()
  setAuthToken(null)
})

function renderIt() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <WatchlistSummary />
      </AuthProvider>
    </MemoryRouter>,
  )
}

function user(overrides: Partial<UserPublic> = {}): UserPublic {
  return { id: 'u1', email: 'trader@example.com', created_at: '2026-01-01T00:00:00Z', ...overrides }
}

describe('WatchlistSummary', () => {
  it('shows a sign-in prompt instead of crashing when anonymous', async () => {
    renderIt()

    expect(await screen.findByText(/Sign in/)).toBeInTheDocument()
    expect(screen.getByText(/to see your watchlist/)).toBeInTheDocument()
  })

  it('shows the tracked tickers when authenticated', async () => {
    setAuthToken('token-1')
    vi.spyOn(authApi, 'fetchCurrentUser').mockResolvedValue(user())
    vi.spyOn(portfolioApi, 'fetchWatchlist').mockResolvedValue([
      { ticker: 'TCS', created_at: '2026-09-01T00:00:00Z' },
      { ticker: 'INFY', created_at: '2026-09-02T00:00:00Z' },
    ])

    renderIt()

    expect(await screen.findByText('2 tickers tracked.')).toBeInTheDocument()
    expect(screen.getByText('TCS')).toBeInTheDocument()
    expect(screen.getByText('INFY')).toBeInTheDocument()
  })

  it('shows an honest empty state rather than nothing', async () => {
    setAuthToken('token-1')
    vi.spyOn(authApi, 'fetchCurrentUser').mockResolvedValue(user())
    vi.spyOn(portfolioApi, 'fetchWatchlist').mockResolvedValue([])

    renderIt()

    expect(await screen.findByText(/Your watchlist is empty/)).toBeInTheDocument()
  })
})
