import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DataSourceStatusProvider, useDataSourceStatus } from './DataSourceStatusContext'
import * as dataSourcesApi from '../api/dataSources'
import type { DataSourceStatus } from '../types/backend'

function source(overrides: Partial<DataSourceStatus> = {}): DataSourceStatus {
  return {
    name: 'screener',
    label: 'Screener',
    type: 'historical/search',
    configured: true,
    status: 'SUCCESS',
    capabilities: [],
    primary_for: [],
    fallback_for: [],
    last_success_at: null,
    last_error_at: null,
    limitation: null,
    ...overrides,
  }
}

function Consumer({ label }: { label: string }) {
  const { phase, sources } = useDataSourceStatus()
  return (
    <div>
      {label}: {phase} · {sources?.length ?? 'none'}
    </div>
  )
}

function setVisibility(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, value: hidden })
}

/** RTL's `waitFor`/`findBy` poll using real timers, which never fire once
 * fake timers are installed -- so every wait here is an explicit,
 * timer-aware flush instead. */
async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('DataSourceStatusProvider', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setVisibility(false)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('fetches once for two simultaneously-mounted consumers, not once each', async () => {
    const fetchSpy = vi.spyOn(dataSourcesApi, 'fetchDataSourceStatus').mockResolvedValue({ sources: [source()] })

    render(
      <DataSourceStatusProvider>
        <Consumer label="badge" />
        <Consumer label="panel" />
      </DataSourceStatusProvider>,
    )
    await flush()

    expect(screen.getByText(/badge: ready/)).toBeInTheDocument()
    expect(screen.getByText(/panel: ready/)).toBeInTheDocument()
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('polls again after the interval elapses while the tab is visible', async () => {
    const fetchSpy = vi.spyOn(dataSourcesApi, 'fetchDataSourceStatus').mockResolvedValue({ sources: [source()] })
    render(
      <DataSourceStatusProvider>
        <Consumer label="badge" />
      </DataSourceStatusProvider>,
    )
    await flush()
    expect(fetchSpy).toHaveBeenCalledTimes(1)

    await flush(5 * 60 * 1000)
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })

  it('skips the poll tick while the tab is hidden', async () => {
    const fetchSpy = vi.spyOn(dataSourcesApi, 'fetchDataSourceStatus').mockResolvedValue({ sources: [source()] })
    render(
      <DataSourceStatusProvider>
        <Consumer label="badge" />
      </DataSourceStatusProvider>,
    )
    await flush()
    expect(fetchSpy).toHaveBeenCalledTimes(1)

    setVisibility(true)
    await flush(5 * 60 * 1000)
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('refetches on window focus', async () => {
    const fetchSpy = vi.spyOn(dataSourcesApi, 'fetchDataSourceStatus').mockResolvedValue({ sources: [source()] })
    render(
      <DataSourceStatusProvider>
        <Consumer label="badge" />
      </DataSourceStatusProvider>,
    )
    await flush()
    expect(fetchSpy).toHaveBeenCalledTimes(1)

    await flush(15 * 1000)
    await act(async () => {
      window.dispatchEvent(new Event('focus'))
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })

  it('does not double-fire when focus and visibilitychange both land within the debounce window', async () => {
    const fetchSpy = vi.spyOn(dataSourcesApi, 'fetchDataSourceStatus').mockResolvedValue({ sources: [source()] })
    render(
      <DataSourceStatusProvider>
        <Consumer label="badge" />
      </DataSourceStatusProvider>,
    )
    await flush()
    expect(fetchSpy).toHaveBeenCalledTimes(1)

    await flush(15 * 1000)
    setVisibility(false)
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
      window.dispatchEvent(new Event('focus'))
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })

  it('reports the error phase, not a stale success, when the fetch fails', async () => {
    vi.spyOn(dataSourcesApi, 'fetchDataSourceStatus').mockRejectedValue(new Error('network'))
    render(
      <DataSourceStatusProvider>
        <Consumer label="badge" />
      </DataSourceStatusProvider>,
    )
    await flush()

    expect(screen.getByText(/badge: error/)).toBeInTheDocument()
  })
})
