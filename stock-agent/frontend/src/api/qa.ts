import { postJson } from './client'
import type { QAResult, QATickerRequest } from '../types/backend'

/**
 * Asks a free-form question about `ticker`. This is the only place in
 * the app that knows the Q&A endpoint's URL/shape.
 */
export async function askTickerQuestion(ticker: string, question: string): Promise<QAResult> {
  const body: QATickerRequest = { ticker: ticker.trim().toUpperCase(), question: question.trim() }
  return postJson<QAResult>('/api/v1/qa/ticker', body)
}
