import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ScreenerCookieCard } from './ScreenerCookieCard'
import * as marketHistoryApi from '../../api/marketHistory'
import type { ScreenerCookieStatus } from '../../types/backend'

function status(overrides: Partial<ScreenerCookieStatus> = {}): ScreenerCookieStatus {
  return {
    configured: true,
    source: 'runtime',
    status: 'SUCCESS',
    last_validated_at: null,
    last_success_at: null,
    last_error_at: null,
    detail: null,
    ...overrides,
  }
}

describe('ScreenerCookieCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows Not configured when no cookie is stored', async () => {
    vi.spyOn(marketHistoryApi, 'fetchScreenerCookieStatus').mockResolvedValue(status({ configured: false, source: null, status: 'NOT_CONFIGURED' }))
    render(<ScreenerCookieCard />)
    expect(await screen.findByText('Not configured')).toBeInTheDocument()
  })

  it('shows Expired for an auth-expired cookie, never the value itself', async () => {
    vi.spyOn(marketHistoryApi, 'fetchScreenerCookieStatus').mockResolvedValue(status({ status: 'AUTH_EXPIRED' }))
    render(<ScreenerCookieCard />)
    expect(await screen.findByText(/Expired/)).toBeInTheDocument()
  })

  it('never echoes the pasted cookie value anywhere in the DOM after saving', async () => {
    const secret = 'super-secret-session-value-12345'
    vi.spyOn(marketHistoryApi, 'fetchScreenerCookieStatus').mockResolvedValue(status({ configured: false, source: null, status: 'NOT_CONFIGURED' }))
    vi.spyOn(marketHistoryApi, 'setScreenerCookie').mockResolvedValue(status({ status: 'SUCCESS' }))
    render(<ScreenerCookieCard />)

    await screen.findByText('Not configured')
    const input = screen.getByPlaceholderText(/Paste sessionid cookie value/)
    await userEvent.type(input, secret)
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(marketHistoryApi.setScreenerCookie).toHaveBeenCalledWith(secret))
    expect(screen.queryByText(secret)).not.toBeInTheDocument()
    expect(screen.queryByDisplayValue(secret)).not.toBeInTheDocument()
  })
})
