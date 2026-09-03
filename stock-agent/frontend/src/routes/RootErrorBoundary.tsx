import { isRouteErrorResponse, useRouteError } from 'react-router-dom'
import { ErrorState } from '../components/ui/ErrorState'

/** Root `errorElement` -- catches render-time errors thrown anywhere in
 * the route tree (e.g. `useStockReport` called outside a ready
 * provider). Never shows a raw stack trace (§19). */
export function RootErrorBoundary() {
  const error = useRouteError()
  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : 'Something went wrong loading this page.'

  return (
    <main className="mx-auto flex max-w-lg flex-col gap-4 px-4 py-20">
      <ErrorState title="Something went wrong" error={message} onRetry={() => window.location.reload()} />
    </main>
  )
}
