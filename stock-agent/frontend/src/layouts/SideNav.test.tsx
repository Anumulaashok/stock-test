import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { SideNav } from './SideNav'
import * as authContext from '../auth/AuthContext'
import { DataSourceStatusProvider } from '../dataSources/DataSourceStatusContext'

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
})
