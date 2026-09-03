import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, afterEach } from 'vitest'

import DataSourcesPanel from './DataSourcesPanel'
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
    capabilities: ['company_search', 'daily_close_series'],
    primary_for: ['historical_price', 'company_search'],
    fallback_for: [],
    last_success_at: new Date().toISOString(),
    last_error_at: null,
    limitation: null,
    ...overrides,
  }
}

describe('DataSourcesPanel', () => {
  it('shows each source with its status and role', async () => {
    mocked.mockResolvedValue({
      sources: [
        source(),
        source({
          name: 'yfinance',
          label: 'yfinance',
          status: 'SUCCESS',
          primary_for: ['market_quote'],
          limitation: null,
        }),
      ],
    })

    render(<DataSourcesPanel />)

    expect(await screen.findByText('Screener')).toBeInTheDocument()
    expect(screen.getByText('yfinance')).toBeInTheDocument()
    expect(screen.getAllByText('Connected')).toHaveLength(2)
    expect(screen.getByText(/Historical, Search · Primary/)).toBeInTheDocument()
  })

  it('surfaces an expired Screener cookie and says fallback is active', async () => {
    mocked.mockResolvedValue({
      sources: [source({ status: 'AUTH_EXPIRED', last_success_at: null })],
    })

    render(<DataSourcesPanel />)

    expect(await screen.findByText('Expired')).toBeInTheDocument()
    expect(screen.getByText(/Screener unavailable — fallback active/)).toBeInTheDocument()
  })

  it('does not show an unconfigured source as healthy', async () => {
    mocked.mockResolvedValue({
      sources: [source({ configured: false, status: 'NOT_CONFIGURED', last_success_at: null })],
    })

    render(<DataSourcesPanel />)

    expect(await screen.findByText('Not configured')).toBeInTheDocument()
    expect(screen.queryByText('Connected')).not.toBeInTheDocument()
    // An unconfigured source is not a degraded one -- no false alarm banner.
    expect(screen.queryByText(/fallback active/)).not.toBeInTheDocument()
  })

  it('discloses a known limitation on an otherwise healthy source', async () => {
    mocked.mockResolvedValue({
      sources: [
        source({
          name: 'fmp',
          label: 'FMP',
          status: 'SUCCESS',
          primary_for: [],
          fallback_for: ['market_quote'],
          limitation: 'Returns HTTP 402 for every NSE/BSE symbol.',
        }),
      ],
    })

    render(<DataSourcesPanel />)

    expect(await screen.findByText(/Returns HTTP 402/)).toBeInTheDocument()
    expect(screen.getByText(/Market data · Fallback/)).toBeInTheDocument()
  })

  it('reports a failed status fetch instead of rendering a fake healthy state', async () => {
    mocked.mockRejectedValue(new Error('network'))

    render(<DataSourcesPanel />)

    await waitFor(() =>
      expect(screen.getByText('Source status is unavailable.')).toBeInTheDocument(),
    )
    expect(screen.queryByText('Connected')).not.toBeInTheDocument()
  })
})
