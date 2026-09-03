import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
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

  const load = useCallback(
    async (explicitRunId?: string) => {
      setState({ status: 'loading', ticker })
      try {
        const run = explicitRunId
          ? await fetchResearchRun(ticker, explicitRunId)
          : await fetchLatestResearch(ticker)
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
        setState({ status: 'error', ticker, error: toApiError(error) })
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
    void load(researchRunId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [researchRunId])

  const runNew = useCallback(
    async (opts?: { force?: boolean }) => {
      setRefreshing(true)
      try {
        const run = await runResearch(ticker, opts?.force ?? false)
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
        setState({ status: 'error', ticker, error: toApiError(error) })
      } finally {
        setRefreshing(false)
      }
    },
    [ticker],
  )

  const reload = useCallback(
    async (explicitRunId?: string) => {
      setRefreshing(true)
      try {
        await load(explicitRunId)
      } finally {
        setRefreshing(false)
      }
    },
    [load],
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
