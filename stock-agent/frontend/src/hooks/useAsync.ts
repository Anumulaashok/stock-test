import { useEffect, useRef, useState } from 'react'
import { type ApiError, toApiError } from '../api/client'

export type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: ApiError }

/**
 * Small shared replacement for the raw `useState` + `useEffect` +
 * try/catch/finally pattern repeated across every page. Deliberately not
 * a query library -- no cache, no dedup, no refetch-on-focus. Guards
 * against two races the hand-rolled copies didn't: an out-of-order
 * response overwriting a newer one, and setting state after unmount.
 */
export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[],
  opts?: { enabled?: boolean },
): AsyncState<T> & { reload: () => void } {
  const enabled = opts?.enabled ?? true
  const [state, setState] = useState<AsyncState<T>>({ status: 'idle' })
  const requestId = useRef(0)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    if (!enabled) {
      setState({ status: 'idle' })
      return
    }
    const id = ++requestId.current
    let cancelled = false
    setState({ status: 'loading' })
    fn()
      .then((data) => {
        if (cancelled || id !== requestId.current) return
        setState({ status: 'success', data })
      })
      .catch((error: unknown) => {
        if (cancelled || id !== requestId.current) return
        setState({ status: 'error', error: toApiError(error) })
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, reloadToken, ...deps])

  return { ...state, reload: () => setReloadToken((n) => n + 1) }
}
