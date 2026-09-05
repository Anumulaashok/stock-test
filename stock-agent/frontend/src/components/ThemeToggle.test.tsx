import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { ThemeToggle } from './ThemeToggle'
import { ThemeProvider } from '../theme/ThemeContext'

afterEach(() => {
  document.documentElement.removeAttribute('data-theme')
})

describe('ThemeToggle', () => {
  it('offers to switch to light while in dark mode', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    )
    expect(screen.getByRole('button', { name: /switch to light theme/i })).toBeInTheDocument()
  })

  it('switches the page theme and flips its own label when clicked', async () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    )

    await userEvent.click(screen.getByRole('button', { name: /switch to light theme/i }))

    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    expect(screen.getByRole('button', { name: /switch to dark theme/i })).toBeInTheDocument()
  })
})
