import { Link } from 'react-router-dom'
import { paths } from './paths'

export function NotFoundPage() {
  return (
    <main className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="font-mono-nums text-sm text-[var(--color-text-faint)]">404</p>
      <h1 className="text-xl font-bold">Page not found</h1>
      <div className="flex gap-3 text-sm">
        <Link to={paths.home()} className="btn-primary px-3.5 py-1.5">
          Intelligence
        </Link>
        <Link to={paths.discover()} className="btn-secondary px-3.5 py-1.5">
          Discover
        </Link>
      </div>
    </main>
  )
}
