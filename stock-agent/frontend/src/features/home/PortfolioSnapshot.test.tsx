import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { PortfolioSnapshot } from './PortfolioSnapshot'
import { AuthProvider } from '../../auth/AuthContext'
import { setAuthToken } from '../../api/authToken'
import * as authApi from '../../api/auth'
import * as portfolioApi from '../../api/portfolio'
import type { HoldingWithMarketData, UserPublic } from '../../types/backend'

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
        <PortfolioSnapshot />
      </AuthProvider>
    </MemoryRouter>,
  )
}

function user(overrides: Partial<UserPublic> = {}): UserPublic {
  return { id: 'u1', email: 'trader@example.com', created_at: '2026-01-01T00:00:00Z', ...overrides }
}

function holding(overrides: Partial<HoldingWithMarketData>): HoldingWithMarketData {
  return {
    id: 'h1', ticker: 'TCS', quantity: '10', average_cost: '3000',
    added_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    current_price: '3200', price_status: 'live', market_value: '32000',
    unrealized_gain: '2000', unrealized_gain_percent: '6.67',
    ...overrides,
  }
}

describe('PortfolioSnapshot', () => {
  it('shows a sign-in prompt instead of crashing when anonymous', async () => {
    renderIt()
    expect(await screen.findByText(/Sign in/)).toBeInTheDocument()
    expect(screen.getByText(/to see your portfolio/)).toBeInTheDocument()
  })

  it('shows real invested/value/P&L and a derived winners/losers count when authenticated', async () => {
    stubLocalStorage()
    setAuthToken('token-1')
    vi.spyOn(authApi, 'fetchCurrentUser').mockResolvedValue(user())
    vi.spyOn(portfolioApi, 'fetchPortfolioSummary').mockResolvedValue({
      portfolio_id: 'p1',
      invested_capital: '4280000',
      portfolio_value: '5136000',
      unrealized_gain: '856000',
      unrealized_gain_percent: '20.0',
      warnings: [],
      holdings: [
        holding({ id: 'h1', unrealized_gain: '2000' }),
        holding({ id: 'h2', unrealized_gain: '-500' }),
        holding({ id: 'h3', unrealized_gain: '1500' }),
        holding({ id: 'h4', unrealized_gain: null, current_price: null, price_status: 'unavailable' }),
      ],
    })

    renderIt()

    expect(await screen.findByText('₹42.80 L')).toBeInTheDocument()
    expect(screen.getByText('₹51.36 L')).toBeInTheDocument()
    expect(screen.getByText('₹8.56 L (+20.0%)')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument() // winners
    expect(screen.getByText('1')).toBeInTheDocument() // losers
  })

  it('shows an honest empty state rather than nothing', async () => {
    stubLocalStorage()
    setAuthToken('token-1')
    vi.spyOn(authApi, 'fetchCurrentUser').mockResolvedValue(user())
    vi.spyOn(portfolioApi, 'fetchPortfolioSummary').mockResolvedValue({
      portfolio_id: 'p1', invested_capital: '0', portfolio_value: null,
      unrealized_gain: null, unrealized_gain_percent: null, warnings: [], holdings: [],
    })

    renderIt()

    expect(await screen.findByText(/No holdings yet/)).toBeInTheDocument()
  })
})
