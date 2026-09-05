import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, afterEach } from 'vitest'
import { SideNavHealthBadge } from './SideNavHealthBadge'
import { DataSourceStatusProvider } from '../dataSources/DataSourceStatusContext'
import { renderWithRouter } from '../test/renderWithRouter'
import type { DataSourceStatus } from '../types/backend'

vi.mock('../api/dataSources', () => ({ fetchDataSourceStatus: vi.fn() }))
const { fetchDataSourceStatus } = await import('../api/dataSources')
const mocked = vi.mocked(fetchDataSourceStatus)

afterEach(() => vi.resetAllMocks())

function source(overrides: Partial<DataSourceStatus> = {}): DataSourceStatus {
  return {
    name: 'screener',
    label: 'Screener',
    type: 'historical/search',
    configured: true,
    status: 'SUCCESS',
    capabilities: [],
    primary_for: ['historical_price'],
    fallback_for: [],
    last_success_at: null,
    last_error_at: null,
    limitation: null,
    ...overrides,
  }
}

function renderBadge() {
  return renderWithRouter(
    <DataSourceStatusProvider>
      <SideNavHealthBadge />
    </DataSourceStatusProvider>,
  )
}

describe('SideNavHealthBadge', () => {
  it('shows "All sources healthy" when every configured source is healthy', async () => {
    mocked.mockResolvedValue({ sources: [source()] })
    renderBadge()
    expect(await screen.findByText('All sources healthy')).toBeInTheDocument()
  })

  it('reads FMP\'s documented 402 limitation as serving normally, not an alarm', async () => {
    mocked.mockResolvedValue({
      sources: [
        source(),
        source({ name: 'fmp', label: 'FMP', limitation: 'Returns HTTP 402 for every NSE/BSE symbol.' }),
      ],
    })
    renderBadge()
    expect(await screen.findByText(/Serving normally/)).toBeInTheDocument()
    expect(screen.queryByText(/needs attention/)).not.toBeInTheDocument()
  })

  it('shows action-required text and a fix link for an expired Screener cookie', async () => {
    mocked.mockResolvedValue({ sources: [source({ status: 'AUTH_EXPIRED' })] })
    renderBadge()
    expect(await screen.findByText(/Screener needs attention/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Screener needs attention/ }))
    expect(screen.getByRole('link', { name: /fix session cookie/i })).toHaveAttribute('href', '/settings/system')
  })

  it('shows an explicit unknown state, not a false healthy or alarm, when the fetch fails', async () => {
    mocked.mockRejectedValue(new Error('network'))
    renderBadge()
    expect(await screen.findByText('Source status unknown')).toBeInTheDocument()
    expect(screen.queryByText('All sources healthy')).not.toBeInTheDocument()
    expect(screen.queryByText(/needs attention/)).not.toBeInTheDocument()
  })

  it('expands to a per-source list on click', async () => {
    mocked.mockResolvedValue({
      sources: [source(), source({ name: 'yfinance', label: 'yfinance', primary_for: ['market_quote'] })],
    })
    renderBadge()
    await screen.findByText('All sources healthy')

    expect(screen.queryByText('yfinance')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /all sources healthy/i }))
    expect(screen.getByText('yfinance')).toBeInTheDocument()
  })
})
