import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderWithRouter } from '../../test/renderWithRouter'
import { HoldingsTable } from './HoldingsTable'
import * as portfolioApi from '../../api/portfolio'
import { ApiError } from '../../api/client'
import type { HoldingWithMarketData } from '../../types/backend'

function buildHolding(overrides: Partial<HoldingWithMarketData> = {}): HoldingWithMarketData {
  return {
    id: 'h1',
    ticker: 'ACME',
    quantity: '10',
    average_cost: '100',
    added_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    current_price: '120',
    price_status: 'live',
    market_value: '1200',
    unrealized_gain: '200',
    unrealized_gain_percent: '20',
    ...overrides,
  }
}

describe('HoldingsTable', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows an honest empty state', () => {
    renderWithRouter(<HoldingsTable holdings={[]} onDelete={vi.fn()} onChanged={vi.fn()} />)
    expect(screen.getByText(/no holdings yet/i)).toBeInTheDocument()
  })

  it('links the ticker to its stock page', () => {
    renderWithRouter(<HoldingsTable holdings={[buildHolding()]} onDelete={vi.fn()} onChanged={vi.fn()} />)
    expect(screen.getByRole('link', { name: 'ACME' })).toHaveAttribute('href', '/stock/ACME')
  })

  it('shows price_status honestly, including "unavailable"', () => {
    renderWithRouter(
      <HoldingsTable
        holdings={[buildHolding({ current_price: null, price_status: 'unavailable', market_value: null, unrealized_gain: null, unrealized_gain_percent: null })]}
        onDelete={vi.fn()}
        onChanged={vi.fn()}
      />,
    )
    expect(screen.getByText(/\(unavailable\)/)).toBeInTheDocument()
  })

  it('shows a stale price honestly rather than hiding the status', () => {
    renderWithRouter(<HoldingsTable holdings={[buildHolding({ price_status: 'stale' })]} onDelete={vi.fn()} onChanged={vi.fn()} />)
    expect(screen.getByText(/\(stale\)/)).toBeInTheDocument()
  })

  it('calls onDelete with the holding id when Remove is clicked', async () => {
    const onDelete = vi.fn()
    renderWithRouter(<HoldingsTable holdings={[buildHolding()]} onDelete={onDelete} onChanged={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /remove/i }))
    expect(onDelete).toHaveBeenCalledWith('h1')
  })

  it('edits a holding inline and calls onChanged after saving', async () => {
    const updateSpy = vi.spyOn(portfolioApi, 'updateHolding').mockResolvedValue(buildHolding())
    const onChanged = vi.fn()
    renderWithRouter(<HoldingsTable holdings={[buildHolding()]} onDelete={vi.fn()} onChanged={onChanged} />)

    await userEvent.click(screen.getByRole('button', { name: /edit/i }))
    const quantityInput = screen.getByLabelText(/quantity for acme/i)
    await userEvent.clear(quantityInput)
    await userEvent.type(quantityInput, '15')
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith('h1', { quantity: '15', average_cost: '100' }))
    expect(onChanged).toHaveBeenCalledTimes(1)
  })

  it('rejects a non-positive quantity without calling the API', async () => {
    const updateSpy = vi.spyOn(portfolioApi, 'updateHolding')
    renderWithRouter(<HoldingsTable holdings={[buildHolding()]} onDelete={vi.fn()} onChanged={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: /edit/i }))
    const quantityInput = screen.getByLabelText(/quantity for acme/i)
    await userEvent.clear(quantityInput)
    await userEvent.type(quantityInput, '0')
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    expect(screen.getByText(/must be positive numbers/i)).toBeInTheDocument()
    expect(updateSpy).not.toHaveBeenCalled()
  })

  it('surfaces an API error from a failed edit', async () => {
    vi.spyOn(portfolioApi, 'updateHolding').mockRejectedValue(new ApiError('Ticker not found.', 'client', 404))
    renderWithRouter(<HoldingsTable holdings={[buildHolding()]} onDelete={vi.fn()} onChanged={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: /edit/i }))
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    expect(await screen.findByText('Ticker not found.')).toBeInTheDocument()
  })

  it('cancels an edit without calling the API', async () => {
    const updateSpy = vi.spyOn(portfolioApi, 'updateHolding')
    renderWithRouter(<HoldingsTable holdings={[buildHolding()]} onDelete={vi.fn()} onChanged={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: /edit/i }))
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))

    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
    expect(updateSpy).not.toHaveBeenCalled()
  })
})
