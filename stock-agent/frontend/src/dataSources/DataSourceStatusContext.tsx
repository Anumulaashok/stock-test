import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { fetchDataSourceStatus } from '../api/dataSources'
import type { DataSourceStatus } from '../types/backend'

export type DataSourceStatusPhase = 'loading' | 'ready' | 'error'

interface DataSourceStatusContextValue {
  phase: DataSourceStatusPhase
  sources: DataSourceStatus[] | null
  reload: () => void
}

const DataSourceStatusContext = createContext<DataSourceStatusContextValue | null>(null)

/** How often to poll while the tab is visible. This is the one endpoint
 * in the app where that's appropriate: it reads an in-memory health
 * cache on the backend, not a metered provider, so a 5-minute poll plus
 * a refetch on tab focus/visibility-return costs one cheap local
 * request every few minutes -- not FMP/Finnhub/IndianAPI quota. */
const POLL_INTERVAL_MS = 5 * 60 * 1000
/** Debounces focus + visibilitychange firing back to back for the same
 * tab-switch, without suppressing a deliberate manual "Refresh" click. */
const MIN_AUTO_REFETCH_GAP_MS = 10 * 1000

/**
 * Single shared fetch of `GET /api/v1/market/data-sources/status` for
 * the whole app. Mounted once in `AppShell`, above both the sidebar
 * health badge and the Settings data-sources panel, so two
 * simultaneously-mounted consumers never each fire their own request
 * for the same data.
 */
export function DataSourceStatusProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<DataSourceStatusPhase>('loading')
  const [sources, setSources] = useState<DataSourceStatus[] | null>(null)
  const lastFetchStartedAt = useRef(0)
  const inFlight = useRef(false)

  const fetchNow = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    lastFetchStartedAt.current = Date.now()
    try {
      const response = await fetchDataSourceStatus()
      setSources(response.sources)
      setPhase('ready')
    } catch {
      setSources(null)
      setPhase('error')
    } finally {
      inFlight.current = false
    }
  }, [])

  const autoFetch = useCallback(() => {
    if (Date.now() - lastFetchStartedAt.current < MIN_AUTO_REFETCH_GAP_MS) return
    void fetchNow()
  }, [fetchNow])

  useEffect(() => {
    void fetchNow()

    const interval = window.setInterval(() => {
      if (document.hidden) return
      autoFetch()
    }, POLL_INTERVAL_MS)

    function onVisibilityChange() {
      if (!document.hidden) autoFetch()
    }
    function onFocus() {
      autoFetch()
    }

    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('focus', onFocus)
    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      window.removeEventListener('focus', onFocus)
    }
  }, [fetchNow, autoFetch])

  const reload = useCallback(() => {
    void fetchNow()
  }, [fetchNow])

  return (
    <DataSourceStatusContext.Provider value={{ phase, sources, reload }}>{children}</DataSourceStatusContext.Provider>
  )
}

export function useDataSourceStatus(): DataSourceStatusContextValue {
  const ctx = useContext(DataSourceStatusContext)
  if (!ctx) throw new Error('useDataSourceStatus must be used within a DataSourceStatusProvider')
  return ctx
}
