import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, it, expect, vi } from 'vitest'
import { SearchBar } from './SearchBar'
import * as searchApi from '../api/search'
import type { StockSearchResult } from '../api/search'

const RELIANCE: StockSearchResult = { symbol: 'RELIANCE', name: 'Reliance Industries Limited', exchange: 'NSE', isin: 'INE002A01018' }

describe('SearchBar', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('submits the typed value directly when the user presses Analyze', async () => {
    vi.spyOn(searchApi, 'searchStocksWithScreenerFallback').mockResolvedValue([])
    const onSubmit = vi.fn()
    render(<SearchBar onSubmit={onSubmit} disabled={false} />)

    await userEvent.type(screen.getByLabelText(/ticker symbol/i), 'ACME')
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(onSubmit).toHaveBeenCalledWith('ACME')
  })

  it('shows suggestions from the search API and submits the selected one', async () => {
    vi.spyOn(searchApi, 'searchStocksWithScreenerFallback').mockResolvedValue([RELIANCE])
    const onSubmit = vi.fn()
    render(<SearchBar onSubmit={onSubmit} disabled={false} />)

    await userEvent.type(screen.getByLabelText(/ticker symbol/i), 'RELIA')

    const option = await screen.findByRole('option', { name: /reliance industries limited/i })
    await userEvent.click(option)

    expect(onSubmit).toHaveBeenCalledWith('RELIANCE')
    expect(screen.getByLabelText(/ticker symbol/i)).toHaveValue('RELIANCE')
  })

  it('does not query the search API for an empty or whitespace-only value', async () => {
    const spy = vi.spyOn(searchApi, 'searchStocksWithScreenerFallback').mockResolvedValue([])
    render(<SearchBar onSubmit={vi.fn()} disabled={false} />)

    await userEvent.type(screen.getByLabelText(/ticker symbol/i), '   ')

    // A whitespace-only value never schedules a debounced lookup at
    // all (checked synchronously in the effect), so there's nothing to
    // wait for here.
    expect(spy).not.toHaveBeenCalled()
  })

  it('selects a highlighted suggestion with the keyboard', async () => {
    vi.spyOn(searchApi, 'searchStocksWithScreenerFallback').mockResolvedValue([RELIANCE])
    const onSubmit = vi.fn()
    render(<SearchBar onSubmit={onSubmit} disabled={false} />)

    const input = screen.getByLabelText(/ticker symbol/i)
    await userEvent.type(input, 'RELIA')
    await screen.findByRole('option', { name: /reliance industries limited/i })

    await userEvent.keyboard('{ArrowDown}{Enter}')

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith('RELIANCE'))
  })

  it('disables the input and button when disabled is true', () => {
    vi.spyOn(searchApi, 'searchStocksWithScreenerFallback').mockResolvedValue([])
    render(<SearchBar onSubmit={vi.fn()} disabled={true} />)

    expect(screen.getByLabelText(/ticker symbol/i)).toBeDisabled()
    expect(screen.getByRole('button', { name: /analyzing/i })).toBeDisabled()
  })
})
