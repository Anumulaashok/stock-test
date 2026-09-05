import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { renderWithRouter } from '../test/renderWithRouter'
import { AlertsPage } from './AlertsPage'
import * as alertsApi from '../api/alerts'
import type { Alert } from '../types/alerts'

function alert(overrides: Partial<Alert> = {}): Alert {
  return {
    id: 'alert-1', ticker: 'ACME', condition_type: 'PRICE_ABOVE', threshold_value: '100',
    is_active: true, created_at: '2026-08-01T00:00:00+00:00', updated_at: '2026-08-01T00:00:00+00:00',
    ...overrides,
  }
}

describe('AlertsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('automatically checks alerts once when the page opens, per D6', async () => {
    vi.spyOn(alertsApi, 'fetchAlerts').mockResolvedValue([alert()])
    const evaluateSpy = vi.spyOn(alertsApi, 'evaluateAlerts').mockResolvedValue({
      checked_at: '2026-08-02T00:00:00+00:00',
      evaluations: [{ alert_id: 'alert-1', ticker: 'ACME', condition_type: 'PRICE_ABOVE', status: 'met', observed_value: '150', newly_triggered: true }],
    })

    renderWithRouter(<AlertsPage />)

    await waitFor(() => expect(evaluateSpy).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/condition met/i)).toBeInTheDocument()
  })

  it('states plainly that this is a check-on-open, not continuous monitoring', async () => {
    vi.spyOn(alertsApi, 'fetchAlerts').mockResolvedValue([])
    vi.spyOn(alertsApi, 'evaluateAlerts').mockResolvedValue({ checked_at: '2026-08-02T00:00:00+00:00', evaluations: [] })

    renderWithRouter(<AlertsPage />)

    expect(await screen.findByText(/not continuously in the background/i)).toBeInTheDocument()
  })

  it('re-checks only when "Check now" is clicked, not again on its own', async () => {
    vi.spyOn(alertsApi, 'fetchAlerts').mockResolvedValue([alert()])
    const evaluateSpy = vi.spyOn(alertsApi, 'evaluateAlerts').mockResolvedValue({ checked_at: '2026-08-02T00:00:00+00:00', evaluations: [] })

    renderWithRouter(<AlertsPage />)
    await waitFor(() => expect(evaluateSpy).toHaveBeenCalledTimes(1))

    await userEvent.click(screen.getByRole('button', { name: /check now/i }))
    await waitFor(() => expect(evaluateSpy).toHaveBeenCalledTimes(2))
  })

  it('creating an alert reloads the list', async () => {
    const items: Alert[] = []
    vi.spyOn(alertsApi, 'fetchAlerts').mockImplementation(async () => [...items])
    vi.spyOn(alertsApi, 'evaluateAlerts').mockResolvedValue({ checked_at: '2026-08-02T00:00:00+00:00', evaluations: [] })
    vi.spyOn(alertsApi, 'createAlert').mockImplementation(async (request) => {
      const created = alert({ ticker: request.ticker, condition_type: request.condition_type, threshold_value: request.threshold_value ?? null })
      items.push(created)
      return created
    })

    renderWithRouter(<AlertsPage />)
    await screen.findByText(/no alerts yet/i)

    await userEvent.type(screen.getByLabelText(/ticker/i), 'acme')
    await userEvent.type(screen.getByLabelText(/threshold/i), '100')
    await userEvent.click(screen.getByRole('button', { name: /add alert/i }))

    await waitFor(() => expect(screen.getByText('ACME')).toBeInTheDocument())
  })
})
