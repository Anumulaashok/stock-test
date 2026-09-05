import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AddAlertForm } from './AddAlertForm'

describe('AddAlertForm', () => {
  it('shows a threshold field for a threshold condition, hides it for regime change', async () => {
    render(<AddAlertForm onAdd={vi.fn()} />)
    expect(screen.getByLabelText(/threshold/i)).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText(/condition/i), 'Market regime changes')
    expect(screen.queryByLabelText(/threshold/i)).not.toBeInTheDocument()
  })

  it('rejects submission of a threshold condition with no threshold value', async () => {
    const onAdd = vi.fn()
    render(<AddAlertForm onAdd={onAdd} />)

    await userEvent.type(screen.getByLabelText(/ticker/i), 'acme')
    await userEvent.click(screen.getByRole('button', { name: /add alert/i }))

    expect(await screen.findByText(/needs a threshold value/i)).toBeInTheDocument()
    expect(onAdd).not.toHaveBeenCalled()
  })

  it('submits an uppercased ticker and the exact condition/threshold picked', async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined)
    render(<AddAlertForm onAdd={onAdd} />)

    await userEvent.type(screen.getByLabelText(/ticker/i), 'acme')
    await userEvent.selectOptions(screen.getByLabelText(/condition/i), 'Score above')
    await userEvent.type(screen.getByLabelText(/threshold/i), '80')
    await userEvent.click(screen.getByRole('button', { name: /add alert/i }))

    expect(onAdd).toHaveBeenCalledWith({ ticker: 'ACME', condition_type: 'SCORE_ABOVE', threshold_value: '80' })
  })

  it('submits a null threshold for a non-threshold condition', async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined)
    render(<AddAlertForm onAdd={onAdd} />)

    await userEvent.type(screen.getByLabelText(/ticker/i), 'acme')
    await userEvent.selectOptions(screen.getByLabelText(/condition/i), 'Golden cross (50/200-day)')
    await userEvent.click(screen.getByRole('button', { name: /add alert/i }))

    expect(onAdd).toHaveBeenCalledWith({ ticker: 'ACME', condition_type: 'DMA_CROSSOVER_GOLDEN', threshold_value: null })
  })
})
