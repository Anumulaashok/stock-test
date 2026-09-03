import { Link, useMatches } from 'react-router-dom'

export interface RouteHandle {
  crumb?: (params: Record<string, string | undefined>) => string
}

/** Reads `handle.crumb` off every matched route (declared alongside each
 * route in `routes.tsx`) instead of keeping a parallel breadcrumb config
 * that can drift out of sync with the route tree. */
export function Breadcrumbs() {
  const matches = useMatches()
  const crumbs = matches
    .map((match) => {
      const handle = match.handle as RouteHandle | undefined
      const label = handle?.crumb?.(match.params as Record<string, string | undefined>)
      return label ? { label, pathname: match.pathname } : null
    })
    .filter((c): c is { label: string; pathname: string } => c !== null)

  if (crumbs.length <= 1) return null

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-[var(--color-text-faint)]">
      {crumbs.map((crumb, i) => (
        <span key={crumb.pathname} className="flex items-center gap-1.5">
          {i > 0 && <span aria-hidden="true">/</span>}
          {i === crumbs.length - 1 ? (
            <span className="text-[var(--color-text-muted)]">{crumb.label}</span>
          ) : (
            <Link to={crumb.pathname} className="hover:text-[var(--color-text)]">
              {crumb.label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  )
}
