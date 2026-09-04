import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { WatchlistPage } from './WatchlistPage'
import { renderWithRouter } from '../test/renderWithRouter'
import * as portfolioApi from '../api/portfolio'
import { ApiError } from '../api/client'
import { formatDate } from '../lib/format'
import type { WatchlistItemEnriched } from '../types/backend'

function enrichedItem(overrides: Partial<WatchlistItemEnriched> = {}): WatchlistItemEnriched {
  return {
    ticker: 'RELIANCE',
    created_at: '2026-02-15T00:00:00+00:00',
    current_price: null,
    price_status: 'unavailable',
    change_percent: null,
    overall_score: null,
    band: null,
    last_researched_at: null,
    ...overrides,
  }
}

describe('WatchlistPage', () => {
  it('renders each item with its added date and a link to view the stock', async () => {
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockResolvedValue([enrichedItem()])

    renderWithRouter(<WatchlistPage />)

    expect(await screen.findByText('RELIANCE')).toBeInTheDocument()
    expect(screen.getByText(`Added ${formatDate('2026-02-15T00:00:00+00:00')}`)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View' })).toHaveAttribute('href', '/stock/RELIANCE')
  })

  it('shows the live price and change when available', async () => {
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockResolvedValue([
      enrichedItem({ current_price: '2750.5', price_status: 'live', change_percent: '1.25' }),
    ])

    renderWithRouter(<WatchlistPage />)

    expect(await screen.findByText('2750.50')).toBeInTheDocument()
    expect(screen.getByText('+1.3%')).toBeInTheDocument()
  })

  it('shows "Price unavailable" and "Not researched" honestly, never fabricated values', async () => {
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockResolvedValue([enrichedItem()])

    renderWithRouter(<WatchlistPage />)

    expect(await screen.findByText('Price unavailable')).toBeInTheDocument()
    expect(screen.getByText('Not researched')).toBeInTheDocument()
  })

  it('shows the overall score when the ticker has been researched', async () => {
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockResolvedValue([
      enrichedItem({ overall_score: '81', band: 'strong' }),
    ])

    renderWithRouter(<WatchlistPage />)

    expect(await screen.findByText('81')).toBeInTheDocument()
  })

  it('shows an empty state when the watchlist has no items', async () => {
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockResolvedValue([])

    renderWithRouter(<WatchlistPage />)

    expect(await screen.findByText(/your watchlist is empty/i)).toBeInTheDocument()
  })

  it('shows an error with retry when the watchlist fails to load', async () => {
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockRejectedValueOnce(new ApiError('boom', 'server', 500))

    renderWithRouter(<WatchlistPage />)

    expect(await screen.findByText(/could not load your watchlist/i)).toBeInTheDocument()

    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockResolvedValueOnce([])
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))

    expect(await screen.findByText(/your watchlist is empty/i)).toBeInTheDocument()
  })

  it('adds an uppercased ticker and reloads the list', async () => {
    const items: WatchlistItemEnriched[] = []
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockImplementation(async () => items)
    const addSpy = vi.spyOn(portfolioApi, 'addWatchlistItem').mockImplementation(async (ticker) => {
      items.push(enrichedItem({ ticker, created_at: '2026-03-01T00:00:00+00:00' }))
      return { ticker, created_at: '2026-03-01T00:00:00+00:00' }
    })

    renderWithRouter(<WatchlistPage />)
    await screen.findByText(/your watchlist is empty/i)

    await userEvent.type(screen.getByLabelText(/add a ticker/i), 'reliance')
    await userEvent.click(screen.getByRole('button', { name: /add to watchlist/i }))

    expect(addSpy).toHaveBeenCalledWith('RELIANCE')
    await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument())
    expect(screen.getByLabelText(/add a ticker/i)).toHaveValue('')
  })

  it('shows an inline error when adding a ticker fails, without clearing the input', async () => {
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockResolvedValue([])
    vi.spyOn(portfolioApi, 'addWatchlistItem').mockRejectedValue(
      new ApiError('RELIANCE is already on your watchlist.', 'client', 409),
    )

    renderWithRouter(<WatchlistPage />)
    await screen.findByText(/your watchlist is empty/i)

    await userEvent.type(screen.getByLabelText(/add a ticker/i), 'reliance')
    await userEvent.click(screen.getByRole('button', { name: /add to watchlist/i }))

    expect(await screen.findByText(/already on your watchlist/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/add a ticker/i)).toHaveValue('RELIANCE')
  })

  it('requires an explicit confirm before removing an item', async () => {
    const items: WatchlistItemEnriched[] = [enrichedItem()]
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockImplementation(async () => [...items])
    const removeSpy = vi.spyOn(portfolioApi, 'removeWatchlistItem').mockImplementation(async (ticker) => {
      items.splice(
        items.findIndex((item) => item.ticker === ticker),
        1,
      )
    })

    renderWithRouter(<WatchlistPage />)
    const row = (await screen.findByText('RELIANCE')).closest('li') as HTMLElement

    await userEvent.click(within(row).getByRole('button', { name: 'Remove' }))
    expect(within(row).getByText('Remove RELIANCE?')).toBeInTheDocument()
    expect(removeSpy).not.toHaveBeenCalled()

    await userEvent.click(within(row).getByRole('button', { name: 'Confirm' }))

    expect(removeSpy).toHaveBeenCalledWith('RELIANCE')
    await waitFor(() => expect(screen.queryByText('RELIANCE')).not.toBeInTheDocument())
    expect(await screen.findByText(/your watchlist is empty/i)).toBeInTheDocument()
  })

  it('lets a cancelled remove be re-confirmed, and keeps the item on failure', async () => {
    vi.spyOn(portfolioApi, 'fetchWatchlistEnriched').mockResolvedValue([enrichedItem()])
    vi.spyOn(portfolioApi, 'removeWatchlistItem').mockRejectedValue(new ApiError('boom', 'server', 500))

    renderWithRouter(<WatchlistPage />)
    const row = (await screen.findByText('RELIANCE')).closest('li') as HTMLElement

    await userEvent.click(within(row).getByRole('button', { name: 'Remove' }))
    await userEvent.click(within(row).getByRole('button', { name: 'Cancel' }))
    expect(within(row).queryByText('Remove RELIANCE?')).not.toBeInTheDocument()

    await userEvent.click(within(row).getByRole('button', { name: 'Remove' }))
    await userEvent.click(within(row).getByRole('button', { name: 'Confirm' }))

    expect(await within(row).findByText(/server encountered an unexpected error/i)).toBeInTheDocument()
    expect(screen.getByText('RELIANCE')).toBeInTheDocument()
  })
})
