import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { AlertsBell } from './AlertsBell'
import * as alertsApi from '../api/alerts'
import * as authContext from '../auth/AuthContext'
import type { AlertTrigger } from '../types/alerts'

function trigger(overrides: Partial<AlertTrigger> = {}): AlertTrigger {
  return {
    id: 't1', alert_id: 'alert-1', ticker: 'ACME', condition_type: 'PRICE_ABOVE',
    triggered_at: '2026-08-02T00:00:00+00:00', observed_value: '150', acknowledged: false,
    ...overrides,
  }
}

function mockAuth(status: 'authenticated' | 'anonymous') {
  vi.spyOn(authContext, 'useAuth').mockReturnValue({
    status, user: status === 'authenticated' ? { id: 'u1', email: 'a@example.com', created_at: '2026-01-01' } : null,
    login: vi.fn(), signup: vi.fn(), logout: vi.fn(),
  } as never)
}

function renderBell() {
  return render(
    <MemoryRouter>
      <AlertsBell />
    </MemoryRouter>,
  )
}

describe('AlertsBell', () => {
  it('is disabled and does not fetch triggers when signed out', () => {
    mockAuth('anonymous')
    const fetchSpy = vi.spyOn(alertsApi, 'fetchAlertTriggers')
    renderBell()
    expect(screen.getByRole('button')).toBeDisabled()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('shows no badge when there are no unacknowledged triggers', async () => {
    mockAuth('authenticated')
    vi.spyOn(alertsApi, 'fetchAlertTriggers').mockResolvedValue([])
    renderBell()
    await waitFor(() => expect(alertsApi.fetchAlertTriggers).toHaveBeenCalledWith(true))
    expect(screen.queryByText('1')).not.toBeInTheDocument()
  })

  it('shows the unacknowledged count as a badge', async () => {
    mockAuth('authenticated')
    vi.spyOn(alertsApi, 'fetchAlertTriggers').mockResolvedValue([trigger(), trigger({ id: 't2' })])
    renderBell()
    expect(await screen.findAllByText('2')).not.toHaveLength(0)
  })

  it('caps the displayed badge at 9+', async () => {
    mockAuth('authenticated')
    vi.spyOn(alertsApi, 'fetchAlertTriggers').mockResolvedValue(Array.from({ length: 12 }, (_, i) => trigger({ id: `t${i}` })))
    renderBell()
    expect(await screen.findAllByText('9+')).not.toHaveLength(0)
  })

  it('never fires the expensive evaluate-alerts call -- only the cheap trigger read', async () => {
    mockAuth('authenticated')
    vi.spyOn(alertsApi, 'fetchAlertTriggers').mockResolvedValue([])
    const evaluateSpy = vi.spyOn(alertsApi, 'evaluateAlerts')
    renderBell()
    await waitFor(() => expect(alertsApi.fetchAlertTriggers).toHaveBeenCalled())
    expect(evaluateSpy).not.toHaveBeenCalled()
  })
})
