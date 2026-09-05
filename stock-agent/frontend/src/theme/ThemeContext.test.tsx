import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ThemeProvider, useTheme } from './ThemeContext'

function Consumer() {
  const { theme, toggleTheme } = useTheme()
  return (
    <button type="button" onClick={toggleTheme}>
      {theme}
    </button>
  )
}

/** This test environment's `localStorage` global has no real
 * getItem/setItem (confirmed by probing it directly -- every call
 * throws `TypeError: ... is not a function`), so `ThemeProvider`'s own
 * try/catch around persistence is load-bearing, not defensive fluff.
 * Stub in a real in-memory implementation here to actually exercise
 * that persistence path instead of only its fallback branch. */
function stubLocalStorage() {
  const store = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
    removeItem: (key: string) => store.delete(key),
    clear: () => store.clear(),
  })
}

describe('ThemeProvider/useTheme', () => {
  beforeEach(() => {
    stubLocalStorage()
    document.documentElement.removeAttribute('data-theme')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    document.documentElement.removeAttribute('data-theme')
  })

  it('defaults to dark, not a system-preference follow', () => {
    render(
      <ThemeProvider>
        <Consumer />
      </ThemeProvider>,
    )
    expect(screen.getByRole('button')).toHaveTextContent('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('toggles to light and sets data-theme on <html>', async () => {
    render(
      <ThemeProvider>
        <Consumer />
      </ThemeProvider>,
    )
    await userEvent.click(screen.getByRole('button'))

    expect(screen.getByRole('button')).toHaveTextContent('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('persists the choice and restores it on next mount', async () => {
    const { unmount } = render(
      <ThemeProvider>
        <Consumer />
      </ThemeProvider>,
    )
    await userEvent.click(screen.getByRole('button'))
    unmount()

    render(
      <ThemeProvider>
        <Consumer />
      </ThemeProvider>,
    )
    expect(screen.getByRole('button')).toHaveTextContent('light')
  })

  it('does not throw when localStorage is entirely unavailable (e.g. private browsing)', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
    })
    expect(() =>
      render(
        <ThemeProvider>
          <Consumer />
        </ThemeProvider>,
      ),
    ).not.toThrow()
    expect(screen.getByRole('button')).toHaveTextContent('dark')
  })

  it('throws a clear error when used outside a ThemeProvider', () => {
    expect(() => render(<Consumer />)).toThrow(/ThemeProvider/)
  })
})
