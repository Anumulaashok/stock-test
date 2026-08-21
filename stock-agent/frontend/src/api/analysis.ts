import { postJson } from './client'
import type { CombinedAnalysisResult, TickerAnalysisRequest } from '../types/backend'

/**
 * Runs the full backend pipeline for `ticker` and requests the
 * structured Step 9 report. This is the only place in the app that
 * knows the analysis endpoint's URL/shape.
 */
export async function analyzeTicker(ticker: string): Promise<CombinedAnalysisResult> {
  const body: TickerAnalysisRequest = { ticker: ticker.trim().toUpperCase(), include_report: true }
  return postJson<CombinedAnalysisResult>('/api/v1/analyze/ticker', body)
}
