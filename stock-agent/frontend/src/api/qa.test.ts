import { describe, it, expect, vi, afterEach } from 'vitest'
import { askTickerQuestion } from './qa'

describe('askTickerQuestion', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('posts to /api/v1/qa/ticker with an uppercased ticker and trimmed question', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ status: 'success' }) })
    vi.stubGlobal('fetch', fetchMock)

    await askTickerQuestion('aapl', '  Is it doing well?  ')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/qa/ticker',
      expect.objectContaining({
        body: JSON.stringify({ ticker: 'AAPL', question: 'Is it doing well?' }),
      }),
    )
  })
})
