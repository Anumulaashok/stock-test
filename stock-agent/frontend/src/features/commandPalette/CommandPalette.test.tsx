import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CommandPalette, OPEN_COMMAND_PALETTE_EVENT } from './CommandPalette'

const navigateMock = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => navigateMock }
})

describe('CommandPalette', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    navigateMock.mockReset()
  })

  it('is closed by default', () => {
    render(<CommandPalette />, { wrapper: MemoryRouter })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens on Cmd+K and closes on Escape', async () => {
    render(<CommandPalette />, { wrapper: MemoryRouter })
    await userEvent.keyboard('{Meta>}k{/Meta}')
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens when the OPEN_COMMAND_PALETTE_EVENT fires (the visible ⌘K hint button)', async () => {
    render(<CommandPalette />, { wrapper: MemoryRouter })
    window.dispatchEvent(new Event(OPEN_COMMAND_PALETTE_EVENT))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('navigates and closes on a valid command', async () => {
    render(<CommandPalette />, { wrapper: MemoryRouter })
    window.dispatchEvent(new Event(OPEN_COMMAND_PALETTE_EVENT))
    const input = await screen.findByPlaceholderText(/reliance/i)

    await userEvent.type(input, 'compare TCS INFY{Enter}')

    expect(navigateMock).toHaveBeenCalledWith('/compare?tickers=TCS,INFY')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows an inline error and stays open on an invalid command, without navigating', async () => {
    render(<CommandPalette />, { wrapper: MemoryRouter })
    window.dispatchEvent(new Event(OPEN_COMMAND_PALETTE_EVENT))
    const input = await screen.findByPlaceholderText(/reliance/i)

    await userEvent.type(input, 'compare ONLYONE{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent(/2-4 tickers/i)
    expect(navigateMock).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })
})
