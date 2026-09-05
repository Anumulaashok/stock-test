import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AddHoldingForm } from './AddHoldingForm'
import * as portfolioApi from '../../api/portfolio'
import { ApiError } from '../../api/client'
import type { Holding } from '../../types/backend'

const HOLDING: Holding = {
  id: 'h1',
  ticker: 'ACME',
  quantity: '10',
  average_cost: '100',
  added_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

async function fillAndSubmit(ticker: string, quantity: string, averageCost: string) {
  if (ticker) await userEvent.type(screen.getByLabelText(/ticker/i), ticker)
  if (quantity) await userEvent.type(screen.getByLabelText(/quantity/i), quantity)
  if (averageCost) await userEvent.type(screen.getByLabelText(/avg cost/i), averageCost)
  await userEvent.click(screen.getByRole('button', { name: /add holding/i }))
}

describe('AddHoldingForm', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('submits a valid holding and clears the form', async () => {
    const addSpy = vi.spyOn(portfolioApi, 'addHolding').mockResolvedValue(HOLDING)
    const onAdded = vi.fn()
    render(<AddHoldingForm onAdded={onAdded} />)

    await fillAndSubmit('acme', '10', '100')

    await waitFor(() => expect(addSpy).toHaveBeenCalledWith('ACME', '10', '100'))
    expect(onAdded).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText(/^ticker$/i)).toHaveValue('')
  })

  it('rejects a zero quantity without calling the API', async () => {
    const addSpy = vi.spyOn(portfolioApi, 'addHolding')
    render(<AddHoldingForm onAdded={vi.fn()} />)

    await fillAndSubmit('ACME', '0', '100')

    expect(screen.getByText(/must be positive numbers/i)).toBeInTheDocument()
    expect(addSpy).not.toHaveBeenCalled()
  })

  it('rejects a negative average cost without calling the API', async () => {
    const addSpy = vi.spyOn(portfolioApi, 'addHolding')
    render(<AddHoldingForm onAdded={vi.fn()} />)

    await fillAndSubmit('ACME', '10', '-5')

    expect(screen.getByText(/must be positive numbers/i)).toBeInTheDocument()
    expect(addSpy).not.toHaveBeenCalled()
  })

  it('surfaces an API error from a failed submission', async () => {
    vi.spyOn(portfolioApi, 'addHolding').mockRejectedValue(new ApiError('Ticker not found.', 'client', 404))
    render(<AddHoldingForm onAdded={vi.fn()} />)

    await fillAndSubmit('BADTICK', '10', '100')

    expect(await screen.findByText('Ticker not found.')).toBeInTheDocument()
  })
})
