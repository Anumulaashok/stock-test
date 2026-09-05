import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { WatchlistSummary } from './WatchlistSummary'
import { AuthProvider } from '../../auth/AuthContext'
import { setAuthToken } from '../../api/authToken'
import * as authApi from '../../api/auth'
import * as portfolioApi from '../../api/portfolio'
import type { UserPublic } from '../../types/backend'

/** This test env's real `localStorage` has no working methods (see
 * project memory) -- `setAuthToken` would otherwise silently no-op,
 * leaving `AuthProvider` stuck reporting "anonymous". Stub a real
 * in-memory implementation for the "authenticated" tests below. */
function stubLocalStorage() {
  const store = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
    clear: () => store.clear(),
  })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
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

  it('shows real price/change/score data for tracked tickers when authenticated', async () => {
    stubLocalStorage()
    setAuthToken('token-1')
    vi.spyOn(authApi, 'fetchCurrentUser').mockResolvedValue(user())
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockResolvedValue([
      {
        ticker: 'TCS', created_at: '2026-09-01T00:00:00Z',
        current_price: '4200.50', price_status: 'live', change_percent: '1.25',
        overall_score: '70', band: 'strong', last_researched_at: '2026-09-05T00:00:00Z',
      },
      {
        ticker: 'INFY', created_at: '2026-09-02T00:00:00Z',
        current_price: null, price_status: 'unavailable', change_percent: null,
        overall_score: null, band: null, last_researched_at: null,
      },
    ])

    renderIt()

    expect(await screen.findByText('TCS')).toBeInTheDocument()
    expect(screen.getByText('₹4,200.5')).toBeInTheDocument()
    expect(screen.getByText('+1.3%')).toBeInTheDocument()
    expect(screen.getByText('70')).toBeInTheDocument()
    expect(screen.getByText('INFY')).toBeInTheDocument()
  })

  it('shows an honest empty state rather than nothing', async () => {
    stubLocalStorage()
    setAuthToken('token-1')
    vi.spyOn(authApi, 'fetchCurrentUser').mockResolvedValue(user())
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockResolvedValue([])

    renderIt()

    expect(await screen.findByText(/Your watchlist is empty/)).toBeInTheDocument()
  })
})
