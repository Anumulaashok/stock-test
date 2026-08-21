/**
 * Low-level HTTP client. Every request in the app goes through here so
 * error handling (timeouts, network failures, HTTP status codes, and
 * never exposing a raw stack trace) is defined once, not scattered
 * across components.
 */

export class ApiError extends Error {
  readonly status: number | null
  readonly kind: 'network' | 'timeout' | 'client' | 'server'

  constructor(message: string, kind: ApiError['kind'], status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
  }
}

const DEFAULT_TIMEOUT_MS = 120_000 // the analyst LLM call alone can take ~1-2 minutes (CPU-only server)

async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    // FastAPI validation errors: {"detail": [{"msg": "...", "loc": [...]}, ...]}
    if (Array.isArray(body?.detail)) {
      return body.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join('; ')
    }
    if (typeof body?.detail === 'string') return body.detail
    if (typeof body?.message === 'string') return body.message
  } catch {
    // Response wasn't JSON -- fall through to a generic message below.
  }
  return `Request failed with status ${response.status}`
}

export async function postJson<TResponse>(
  path: string,
  body: unknown,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<TResponse> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)

  let response: Response
  try {
    response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('The request took too long and was cancelled.', 'timeout')
    }
    throw new ApiError('Could not reach the analysis server. Check your connection.', 'network')
  } finally {
    clearTimeout(timeout)
  }

  if (!response.ok) {
    const message = await extractErrorMessage(response)
    const kind = response.status >= 500 ? 'server' : 'client'
    throw new ApiError(message, kind, response.status)
  }

  return (await response.json()) as TResponse
}
