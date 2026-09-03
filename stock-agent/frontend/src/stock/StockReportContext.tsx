import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { fetchLatestResearch, fetchResearchRun, runResearch } from '../api/research'
import { ApiError, toApiError } from '../api/client'
import type { InvestmentResearchReport, ResearchRunResult } from '../types/backend'

export type StockReportState =
  | { status: 'loading'; ticker: string }
  | { status: 'error'; ticker: string; error: ApiError }
  | { status: 'empty'; ticker: string }
  | { status: 'ready'; ticker: string; run: ResearchRunResult; report: InvestmentResearchReport }

interface StockReportContextValue {
  state: StockReportState
  refreshing: boolean
  /** Runs (or reuses) today's snapshot -- the explicit "Run research"
   * action, never fired automatically on a 404 (see runNewOnEmpty note
   * on `load` below). */
  runNew: (opts?: { force?: boolean }) => Promise<void>
  /** Loads a specific past run, or re-loads the latest if `researchRunId`
   * is omitted. */
  reload: (researchRunId?: string) => Promise<void>
}

const StockReportContext = createContext<StockReportContextValue | null>(null)

/**
 * Owns the single fetch of a ticker's `CombinedAnalysisResult` and
 * publishes it to every stock tab via context -- `/stock/:ticker`'s
 * layout route is the only place this is fetched, so switching tabs
 * never refetches (see the redesign plan's "one architectural decision
 * that matters"). Deliberately not a query library: this is the one
 * seam a future TanStack Query adoption would replace, kept behind an
 * unchanged hook signature.
 *
 * A 404 (nothing ever researched for this ticker) becomes `status:
 * 'empty'`, never an automatic `runNew()` call -- a research run can
 * take 1-2 minutes, and firing one on every deep link/refresh/crawler
 * hit would be a surprising, expensive side effect of just visiting a
 * URL. The caller must explicitly trigger `runNew()`.
 */
export function StockReportProvider({
  ticker,
  researchRunId,
  children,
}: {
  ticker: string
  researchRunId?: string
  children: ReactNode
}) {
  const [state, setState] = useState<StockReportState>({ status: 'loading', ticker })
  const [refreshing, setRefreshing] = useState(false)

  // A single monotonic counter guards every state-writing async path
  // below (`load`'s effect, `runNew`) -- `reload(id)` calling `load` can
  // be in flight when `researchRunId` changes underneath it (or when
  // `runNew` is triggered mid-load), and whichever resolves last must
  // never be allowed to overwrite a result from a call that started
  // more recently, regardless of resolution order.
  const requestId = useRef(0)

  /** Every state-writing path funnels through here. Bumps `requestId`
   * once per call and checks it after every await -- whichever call
   * started most recently always wins, regardless of resolution order.
   * `markRefreshing` is false for the initial/ticker-change load (there
   * is nothing to show a spinner over yet) and true for an explicit
   * reload/run over an already-rendered report. */
  const fetchAndSet = useCallback(
    async (fetcher: () => Promise<ResearchRunResult | null>, markRefreshing: boolean) => {
      const id = ++requestId.current
      if (markRefreshing) setRefreshing(true)
      else setState({ status: 'loading', ticker })
      try {
        const run = await fetcher()
        if (id !== requestId.current) return
        if (!run) {
          setState({ status: 'empty', ticker })
          return
        }
        const report = run.result.report
        if (!report) {
          setState({
            status: 'error',
            ticker,
            error: new ApiError('The analysis completed but no structured report was returned.', 'server'),
          })
          return
        }
        setState({ status: 'ready', ticker, run, report })
      } catch (error) {
        if (id !== requestId.current) return
        setState({ status: 'error', ticker, error: toApiError(error) })
      } finally {
        if (markRefreshing && id === requestId.current) setRefreshing(false)
      }
    },
    [ticker],
  )

  // Fetch key is (ticker, researchRunId) -- the provider is remounted
  // with `key={ticker}` by StockLayout, so `ticker` alone changing here
  // never happens; `researchRunId` changing (picking a past run from
  // history, or navigating tabs with `?run=` in the URL) does, and must
  // re-fetch.
  useEffect(() => {
    const fetcher = researchRunId
      ? () => fetchResearchRun(ticker, researchRunId)
      : () => fetchLatestResearch(ticker)
    void fetchAndSet(fetcher, false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [researchRunId])

  const runNew = useCallback(
    (opts?: { force?: boolean }) => fetchAndSet(() => runResearch(ticker, opts?.force ?? false), true),
    [fetchAndSet, ticker],
  )

  const reload = useCallback(
    (explicitRunId?: string) =>
      fetchAndSet(explicitRunId ? () => fetchResearchRun(ticker, explicitRunId) : () => fetchLatestResearch(ticker), true),
    [fetchAndSet, ticker],
  )

  const value = useMemo<StockReportContextValue>(
    () => ({ state, refreshing, runNew, reload }),
    [state, refreshing, runNew, reload],
  )

  return <StockReportContext.Provider value={value}>{children}</StockReportContext.Provider>
}

/** Full state union -- for the layout chrome only (header, banners, tab
 * bar, skeleton/error/empty rendering). Tabs should use `useStockReport`
 * instead. */
export function useStockReportState(): StockReportContextValue {
  const ctx = useContext(StockReportContext)
  if (!ctx) throw new Error('useStockReportState must be used within a StockReportProvider')
  return ctx
}

/** For the eight tab components: the report is guaranteed non-null.
 * `StockLayout` only mounts `<Outlet/>` once `state.status === 'ready'`,
 * so tabs never null-check `report`. */
export function useStockReport(): { ticker: string; run: ResearchRunResult; report: InvestmentResearchReport } {
  const { state } = useStockReportState()
  if (state.status !== 'ready') {
    throw new Error('useStockReport must only be called while the report is ready')
  }
  return { ticker: state.ticker, run: state.run, report: state.report }
}
