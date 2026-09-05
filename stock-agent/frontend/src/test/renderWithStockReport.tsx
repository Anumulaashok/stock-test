import { render, waitFor } from '@testing-library/react'
import { expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { StockReportProvider, useStockReportState } from '../stock/StockReportContext'
import { buildReport, buildRunResult } from './fixtures'
import * as researchApi from '../api/research'
import type { InvestmentResearchReport } from '../types/backend'

/** Mirrors `StockLayoutInner`: only mounts `children` once `status ===
 * 'ready'` (a tab calling `useStockReport()` throws otherwise, exactly
 * like it would in the real app if rendered before the report loads).
 * The hidden probe div lets `renderWithStockReport` wait for readiness
 * deterministically, regardless of what `children` renders. */
function ReadyGate({ children }: { children: ReactNode }) {
  const { state } = useStockReportState()
  return (
    <>
      <div data-testid="stock-report-probe" data-status={state.status} hidden />
      {state.status === 'ready' ? children : null}
    </>
  )
}

/**
 * Renders `children` inside a `StockReportProvider` already resolved to
 * `status: 'ready'`. Every stock tab calls `useStockReport()`, which
 * throws when rendered outside a ready provider -- tab tests need this
 * instead of mounting `StockReportProvider` raw and racing its fetch.
 * Mocks `fetchLatestResearch`; if a test needs `fetchResearchRun`'s
 * `?run=` path instead, mock that directly and skip this helper.
 */
export async function renderWithStockReport(
  children: ReactNode,
  reportOverrides: Partial<InvestmentResearchReport> = {},
) {
  const report = buildReport(reportOverrides)
  vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(buildRunResult(report))

  const utils = render(
    <StockReportProvider ticker={report.company.ticker ?? 'ACME'}>
      <ReadyGate>{children}</ReadyGate>
    </StockReportProvider>,
  )
  await waitFor(() => expect(utils.getByTestId('stock-report-probe')).toHaveAttribute('data-status', 'ready'))
  return { ...utils, report }
}
