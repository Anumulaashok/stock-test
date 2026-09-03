import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useAsync } from './useAsync'
import { ApiError } from '../api/client'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('useAsync', () => {
  it('goes idle -> loading -> success', async () => {
    const { promise, resolve } = deferred<string>()
    const { result } = renderHook(() => useAsync(() => promise, []))

    expect(result.current.status).toBe('loading')

    resolve('hello')
    await waitFor(() => expect(result.current.status).toBe('success'))
    expect(result.current).toMatchObject({ status: 'success', data: 'hello' })
  })

  it('normalizes a non-ApiError rejection through toApiError', async () => {
    const { result } = renderHook(() => useAsync(() => Promise.reject(new Error('boom')), []))

    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current).toMatchObject({ status: 'error', error: { kind: 'network' } })
  })

  it('preserves a real ApiError instance as-is', async () => {
    const apiError = new ApiError('nope', 'client', 400)
    const { result } = renderHook(() => useAsync(() => Promise.reject(apiError), []))

    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.status === 'error' && result.current.error).toBe(apiError)
  })

  it('ignores an out-of-order response from a superseded call', async () => {
    const first = deferred<string>()
    const second = deferred<string>()
    const fn = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    const { result, rerender } = renderHook(({ dep }) => useAsync(fn, [dep]), { initialProps: { dep: 1 } })
    rerender({ dep: 2 })

    // The first (now-superseded) call resolves after the second has
    // already started -- its result must never overwrite the second's.
    first.resolve('stale')
    second.resolve('fresh')

    await waitFor(() => expect(result.current.status).toBe('success'))
    expect(result.current).toMatchObject({ status: 'success', data: 'fresh' })
  })

  it('never fires while disabled, and stays idle', async () => {
    const fn = vi.fn().mockResolvedValue('should not run')
    const { result } = renderHook(() => useAsync(fn, [], { enabled: false }))

    await new Promise((r) => setTimeout(r, 20))
    expect(fn).not.toHaveBeenCalled()
    expect(result.current.status).toBe('idle')
  })

  it('does not update state after unmount', async () => {
    const { promise, resolve } = deferred<string>()
    const { result, unmount } = renderHook(() => useAsync(() => promise, []))

    unmount()
    resolve('too late')
    // No assertion possible on `result.current` post-unmount other than
    // that nothing throws / React logs no act() warning -- the `cancelled`
    // guard inside the effect's cleanup is what's under test here.
    await new Promise((r) => setTimeout(r, 10))
    expect(result.current.status).toBe('loading')
  })

  it('reload() triggers a fresh call', async () => {
    const fn = vi.fn().mockResolvedValueOnce('one').mockResolvedValueOnce('two')
    const { result } = renderHook(() => useAsync(fn, []))

    await waitFor(() => expect(result.current).toMatchObject({ status: 'success', data: 'one' }))

    result.current.reload()

    await waitFor(() => expect(result.current).toMatchObject({ status: 'success', data: 'two' }))
    expect(fn).toHaveBeenCalledTimes(2)
  })
})
