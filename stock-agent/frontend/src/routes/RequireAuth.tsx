import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { paths } from './paths'

/**
 * Pathless layout route gating `/watchlist`, `/portfolio`, and
 * `/settings/*`. UX-only, not a security boundary -- the backend has no
 * `current_user` dependency on the settings-bound routes (screener
 * cookie, historical import). Never redirects while auth status is
 * still `checking`, or a page refresh would flash-redirect every
 * signed-in user to `/login` before their token finishes validating.
 */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'checking') {
    return <div className="p-10 text-center text-sm text-[var(--color-text-faint)]">Checking your session…</div>
  }

  if (status === 'anonymous') {
    return <Navigate to={paths.login()} replace state={{ from: location }} />
  }

  return <Outlet />
}
