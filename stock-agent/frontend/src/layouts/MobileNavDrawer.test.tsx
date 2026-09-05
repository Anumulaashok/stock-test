import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MobileNavDrawer, OPEN_MOBILE_NAV_EVENT } from './MobileNavDrawer'
import * as authContext from '../auth/AuthContext'
import { DataSourceStatusProvider } from '../dataSources/DataSourceStatusContext'

function mockAuth() {
  vi.spyOn(authContext, 'useAuth').mockReturnValue({
    status: 'anonymous', user: null, login: vi.fn(), signup: vi.fn(), logout: vi.fn(),
  } as never)
}

function renderDrawer() {
  return render(
    <MemoryRouter>
      <DataSourceStatusProvider>
        <MobileNavDrawer />
      </DataSourceStatusProvider>
    </MemoryRouter>,
  )
}

describe('MobileNavDrawer', () => {
  beforeEach(() => {
    mockAuth()
  })

  it('is closed by default', () => {
    renderDrawer()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens when OPEN_MOBILE_NAV_EVENT fires', async () => {
    renderDrawer()
    window.dispatchEvent(new Event(OPEN_MOBILE_NAV_EVENT))
    expect(await screen.findByRole('dialog', { name: /navigation/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /discover/i })).toBeInTheDocument()
  })

  it('closes on Escape', async () => {
    renderDrawer()
    window.dispatchEvent(new Event(OPEN_MOBILE_NAV_EVENT))
    await screen.findByRole('dialog')

    await userEvent.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes when a nav link is clicked', async () => {
    renderDrawer()
    window.dispatchEvent(new Event(OPEN_MOBILE_NAV_EVENT))
    await screen.findByRole('dialog')

    await userEvent.click(screen.getByRole('link', { name: /discover/i }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes on backdrop click', async () => {
    renderDrawer()
    window.dispatchEvent(new Event(OPEN_MOBILE_NAV_EVENT))
    const dialog = await screen.findByRole('dialog')

    await userEvent.click(dialog.parentElement!)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
