import { describe, it, expect, vi, afterEach } from 'vitest'
import { postJson, ApiError } from './client'

describe('postJson', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns parsed JSON on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ hello: 'world' }),
      }),
    )

    const result = await postJson<{ hello: string }>('/api/v1/analyze/ticker', { ticker: 'AAPL' })
    expect(result).toEqual({ hello: 'world' })
  })

  it('sends the body as JSON via POST', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchMock)

    await postJson('/api/v1/analyze/ticker', { ticker: 'AAPL', include_report: true })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/analyze/ticker',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: 'AAPL', include_report: true }),
      }),
    )
  })

  it('raises a network ApiError when fetch rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(postJson('/api/v1/analyze/ticker', {})).rejects.toMatchObject({
      name: 'ApiError',
      kind: 'network',
    } satisfies Partial<ApiError>)
  })

  it('extracts FastAPI validation error details for 422 responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: [{ msg: 'field required', loc: ['body', 'ticker'] }] }),
      }),
    )

    await expect(postJson('/api/v1/analyze/ticker', {})).rejects.toMatchObject({
      kind: 'client',
      status: 422,
      message: 'field required',
    })
  })

  it('classifies 5xx responses as server errors without leaking response internals', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('not json')
        },
      }),
    )

    await expect(postJson('/api/v1/analyze/ticker', {})).rejects.toMatchObject({
      kind: 'server',
      status: 500,
    })
  })

  it('never lets a raw stack trace or exception object leak through the message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('boom')
        },
      }),
    )

    try {
      await postJson('/api/v1/analyze/ticker', {})
      expect.unreachable()
    } catch (error) {
      expect((error as ApiError).message).not.toMatch(/Traceback|at Object\.|\.py:/i)
    }
  })
})
