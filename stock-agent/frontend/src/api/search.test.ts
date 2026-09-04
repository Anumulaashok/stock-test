import { afterEach, describe, expect, it, vi } from 'vitest'
import { searchStocksWithScreenerFallback } from './search'
import * as client from './client'
import type { CompanySearchResponse } from '../types/backend'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('searchStocksWithScreenerFallback', () => {
  it('returns the local results without ever calling company-search when the local list has matches', async () => {
    const getJson = vi.spyOn(client, 'getJson').mockResolvedValueOnce([
      { symbol: 'RELIANCE', name: 'Reliance Industries Limited', exchange: 'NSE', isin: 'INE002A01018' },
    ])

    const results = await searchStocksWithScreenerFallback('RELIANCE')

    expect(results).toHaveLength(1)
    expect(getJson).toHaveBeenCalledTimes(1)
    expect(getJson).toHaveBeenCalledWith(expect.stringContaining('/api/v1/search'), expect.anything())
  })

  it('falls back to company-search (Screener) when the local list is empty', async () => {
    const response: CompanySearchResponse = {
      query: 'newco', source: 'screener', source_detail: 'Live Screener.in search (session cookie configured).',
      results: [{ ticker: 'NEWCO', company_name: 'New Co Ltd', screener_company_id: 123, source: 'screener' }],
    }
    const getJson = vi
      .spyOn(client, 'getJson')
      .mockResolvedValueOnce([]) // local /api/v1/search finds nothing
      .mockResolvedValueOnce(response) // Screener fallback finds something

    const results = await searchStocksWithScreenerFallback('newco')

    expect(getJson).toHaveBeenCalledTimes(2)
    expect(results).toEqual([{ symbol: 'NEWCO', name: 'New Co Ltd', exchange: 'Screener', isin: null }])
  })

  it('returns an empty list, never throws, when both the local list and the Screener fallback are empty', async () => {
    const response: CompanySearchResponse = {
      query: 'zzz', source: 'local_directory',
      source_detail: 'No Screener session cookie configured -- local static NSE directory used instead.',
      results: [],
    }
    vi.spyOn(client, 'getJson').mockResolvedValueOnce([]).mockResolvedValueOnce(response)

    const results = await searchStocksWithScreenerFallback('zzz')
    expect(results).toEqual([])
  })

  it('swallows a Screener fallback failure and returns an empty list rather than throwing', async () => {
    vi.spyOn(client, 'getJson')
      .mockResolvedValueOnce([])
      .mockRejectedValueOnce(new Error('Screener unreachable'))

    const results = await searchStocksWithScreenerFallback('anything')
    expect(results).toEqual([])
  })

  it('never fabricates an "NSE" exchange label for a Screener-sourced result', async () => {
    const response: CompanySearchResponse = {
      query: 'infy', source: 'screener', source_detail: 'Live Screener.in search (session cookie configured).',
      results: [{ ticker: 'INFY', company_name: 'Infosys Ltd', screener_company_id: 456, source: 'screener' }],
    }
    vi.spyOn(client, 'getJson').mockResolvedValueOnce([]).mockResolvedValueOnce(response)

    const results = await searchStocksWithScreenerFallback('infy')
    expect(results[0].exchange).toBe('Screener')
    expect(results[0].exchange).not.toBe('NSE')
  })
})
