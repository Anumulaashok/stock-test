import { Outlet } from 'react-router-dom'

/** Login/signup render outside `AppShell` -- the sidebar's Watchlist,
 * Portfolio, and Settings entries are noise on a screen whose entire
 * purpose is to get the visitor signed in. `LoginPage`/`SignupPage`
 * already build their own centered card, so this is a thin passthrough
 * kept as its own layout so that can change without touching the route
 * tree. */
export function AuthLayout() {
  return (
    <div className="min-h-screen text-[var(--color-text)]">
      <Outlet />
    </div>
  )
}
