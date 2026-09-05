import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { AlertsList } from './AlertsList'
import type { Alert, AlertEvaluation } from '../../types/alerts'

function alert(overrides: Partial<Alert> = {}): Alert {
  return {
    id: 'alert-1', ticker: 'ACME', condition_type: 'PRICE_ABOVE', threshold_value: '100',
    is_active: true, created_at: '2026-08-01T00:00:00+00:00', updated_at: '2026-08-01T00:00:00+00:00',
    ...overrides,
  }
}

function renderList(props: Partial<Parameters<typeof AlertsList>[0]> = {}) {
  return render(
    <MemoryRouter>
      <AlertsList alerts={[alert()]} evaluations={new Map()} onToggleActive={vi.fn()} onDelete={vi.fn()} {...props} />
    </MemoryRouter>,
  )
}

describe('AlertsList', () => {
  it('shows an honest empty state, not a fabricated row, when there are no alerts', () => {
    renderList({ alerts: [] })
    expect(screen.getByText(/no alerts yet/i)).toBeInTheDocument()
  })

  it('shows the condition and threshold for an alert', () => {
    renderList()
    expect(screen.getByText(/price above 100/i)).toBeInTheDocument()
  })

  it('shows no evaluation badge when nothing has been checked yet', () => {
    renderList()
    expect(screen.queryByText(/condition met/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/condition not met/i)).not.toBeInTheDocument()
  })

  it('shows the evaluation status and observed value when provided', () => {
    const evaluation: AlertEvaluation = {
      alert_id: 'alert-1', ticker: 'ACME', condition_type: 'PRICE_ABOVE', status: 'met', observed_value: '150', newly_triggered: true,
    }
    renderList({ evaluations: new Map([['alert-1', evaluation]]) })
    expect(screen.getByText(/condition met/i)).toBeInTheDocument()
    expect(screen.getByText(/observed: 150/i)).toBeInTheDocument()
  })

  it('shows "data unavailable," never a false not-met, when the condition could not be checked', () => {
    const evaluation: AlertEvaluation = {
      alert_id: 'alert-1', ticker: 'ACME', condition_type: 'PRICE_ABOVE', status: 'unavailable', observed_value: null, newly_triggered: false,
    }
    renderList({ evaluations: new Map([['alert-1', evaluation]]) })
    expect(screen.getByText(/data unavailable/i)).toBeInTheDocument()
  })

  it('requires explicit confirmation before removing an alert', async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined)
    renderList({ onDelete })

    await userEvent.click(screen.getByRole('button', { name: 'Remove' }))
    expect(screen.getByText('Remove?')).toBeInTheDocument()
    expect(onDelete).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(onDelete).toHaveBeenCalledWith(alert())
  })

  it('toggles active state via the checkbox', async () => {
    const onToggleActive = vi.fn().mockResolvedValue(undefined)
    renderList({ onToggleActive })

    await userEvent.click(screen.getByRole('checkbox', { name: /active/i }))
    expect(onToggleActive).toHaveBeenCalledWith(alert())
  })
})
