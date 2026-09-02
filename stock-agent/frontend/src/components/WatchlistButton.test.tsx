import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { WatchlistButton } from './WatchlistButton'

describe('WatchlistButton', () => {
  it('shows a login hint instead of a toggle when anonymous', () => {
    render(<WatchlistButton status="anonymous" inWatchlist={null} pending={false} error={null} onToggle={vi.fn()} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByTitle(/log in to save/i)).toBeInTheDocument()
  })

  it('offers "Add to Watchlist" when authenticated and not saved', () => {
    render(<WatchlistButton status="authenticated" inWatchlist={false} pending={false} error={null} onToggle={vi.fn()} />)
    expect(screen.getByRole('button', { name: /add to watchlist/i })).toBeInTheDocument()
  })

  it('shows "In Watchlist" and calls onToggle to remove it', async () => {
    const onToggle = vi.fn()
    render(<WatchlistButton status="authenticated" inWatchlist={true} pending={false} error={null} onToggle={onToggle} />)
    const button = screen.getByRole('button', { name: /in watchlist/i })
    expect(button).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(button)
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('disables the button while a request is pending', () => {
    render(<WatchlistButton status="authenticated" inWatchlist={false} pending={true} error={null} onToggle={vi.fn()} />)
    expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled()
  })

  it('surfaces a real error message rather than failing silently', () => {
    render(
      <WatchlistButton status="authenticated" inWatchlist={false} pending={false} error="Could not update your watchlist." onToggle={vi.fn()} />,
    )
    expect(screen.getByText('Could not update your watchlist.')).toBeInTheDocument()
  })
})
