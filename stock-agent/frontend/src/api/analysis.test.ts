import { describe, it, expect, vi, afterEach } from 'vitest'
import { analyzeTicker } from './analysis'

describe('analyzeTicker', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('posts to /api/v1/analyze/ticker with an uppercased ticker, include_report=true, and price-trend forecasting opted in', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ status: 'calculated' }) })
    vi.stubGlobal('fetch', fetchMock)

    await analyzeTicker('aapl')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/analyze/ticker',
      expect.objectContaining({
        body: JSON.stringify({
          ticker: 'AAPL',
          include_report: true,
          include_price_trend_forecast: true,
        }),
      }),
    )
  })
})
