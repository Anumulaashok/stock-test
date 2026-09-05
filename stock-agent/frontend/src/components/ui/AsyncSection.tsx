import type { ReactNode } from 'react'
import type { AsyncState } from '../../hooks/useAsync'
import { ErrorState } from './ErrorState'
import { SkeletonRows } from './Skeleton'

/** Renders the loading/error/success markup for a `useAsync` result once,
 * instead of every section re-declaring its own skeleton/ErrorState block. */
export function AsyncSection<T>({
  state,
  onRetry,
  skeleton,
  errorTitle,
  children,
}: {
  state: AsyncState<T>
  onRetry?: () => void
  skeleton?: ReactNode
  errorTitle?: string
  children: (data: T) => ReactNode
}) {
  if (state.status === 'idle' || state.status === 'loading') {
    return <>{skeleton ?? <SkeletonRows count={4} />}</>
  }
  if (state.status === 'error') {
    return <ErrorState title={errorTitle} error={state.error} onRetry={onRetry} />
  }
  return <>{children(state.data)}</>
}
