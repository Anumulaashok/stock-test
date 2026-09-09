import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SideNav } from './SideNav'
import * as authContext from '../auth/AuthContext'
import { DataSourceStatusProvider } from '../dataSources/DataSourceStatusContext'

/** This test env's real `localStorage` has no working methods (see
 * project memory) -- stub a real in-memory implementation. */
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
  vi.unstubAllGlobals()
})

function mockAuth(status: 'authenticated' | 'anonymous') {
  vi.spyOn(authContext, 'useAuth').mockReturnValue({
    status,
    user: status === 'authenticated' ? { id: 'u1', email: 'a@example.com', created_at: '2026-01-01' } : null,
    login: vi.fn(), signup: vi.fn(), logout: vi.fn(),
  } as never)
}

function renderSideNav() {
  return render(
    <MemoryRouter>
      <DataSourceStatusProvider>
        <SideNav />
      </DataSourceStatusProvider>
    </MemoryRouter>,
  )
}

describe('SideNav', () => {
  it('renders both the full sidebar and the icon rail (visibility is CSS-driven per breakpoint)', () => {
    mockAuth('anonymous')
    renderSideNav()

    // Two "Discover" links exist -- one in the labeled full sidebar, one
    // (label-less, but same href) in the icon-only rail.
    const discoverLinks = screen.getAllByRole('link', { name: /discover/i })
    expect(discoverLinks).toHaveLength(2)
    expect(screen.getByText('Stock Agent')).toBeInTheDocument()
  })

  it('locks an auth-required item for an anonymous user in both layers', () => {
    mockAuth('anonymous')
    renderSideNav()

    expect(document.querySelectorAll('[title="Sign in required"]').length).toBeGreaterThanOrEqual(2)
    expect(screen.queryByRole('link', { name: /watchlist/i })).not.toBeInTheDocument()
  })

  it('unlocks the same item once authenticated', () => {
    mockAuth('authenticated')
    renderSideNav()

    expect(screen.queryByText('Sign in required')).not.toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /watchlist/i }).length).toBeGreaterThanOrEqual(1)
  })

  it('collapses the full sidebar to icon-only on toggle, and persists the choice', () => {
    stubLocalStorage()
    mockAuth('anonymous')
    renderSideNav()

    expect(screen.getByText('Stock Agent')).toBeInTheDocument()

    fireEvent.click(screen.getByTitle('Collapse sidebar'))

    expect(screen.queryByText('Stock Agent')).not.toBeInTheDocument()
    expect(localStorage.getItem('stock-agent-sidenav-collapsed')).toBe('1')

    fireEvent.click(screen.getByTitle('Expand sidebar'))
    expect(screen.getByText('Stock Agent')).toBeInTheDocument()
  })

  it('starts collapsed when a prior session persisted that choice', () => {
    stubLocalStorage()
    localStorage.setItem('stock-agent-sidenav-collapsed', '1')
    mockAuth('anonymous')
    renderSideNav()

    expect(screen.queryByText('Stock Agent')).not.toBeInTheDocument()
    expect(screen.getByTitle('Expand sidebar')).toBeInTheDocument()
  })
})
