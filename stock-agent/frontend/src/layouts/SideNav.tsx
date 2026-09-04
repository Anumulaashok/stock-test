import { NavLink } from 'react-router-dom'
import { paths } from '../routes/paths'
import { Icon, ICON } from '../components/ui/Icon'
import { useAuth } from '../auth/AuthContext'

const NAV_ITEMS: { label: string; icon: string; to: string; requiresAuth?: boolean }[] = [
  { label: 'Intelligence', icon: ICON.core, to: paths.home() },
  { label: 'Discover', icon: ICON.sectors, to: paths.discover() },
  { label: 'Watchlist', icon: ICON.watchlist, to: paths.watchlist(), requiresAuth: true },
  { label: 'Portfolio', icon: ICON.portfolio, to: paths.portfolio(), requiresAuth: true },
  { label: 'Research', icon: ICON.archive, to: paths.research() },
  { label: 'Settings', icon: ICON.settings, to: paths.settings(), requiresAuth: true },
]

/** Not-yet-built roadmap items, shown locked so the roadmap stays
 * visible without linking anywhere. */
const UPCOMING = ['Screener', 'Alerts', 'News']

export function SideNav() {
  const { status } = useAuth()

  return (
    <aside className="hidden w-60 shrink-0 flex-col gap-6 border-r border-[var(--color-border)] px-4 py-6 lg:flex">
      <NavLink to={paths.home()} className="flex items-center gap-2 px-1 text-left">
        <span
          aria-hidden="true"
          className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-gradient-to-br from-[var(--intel-violet)] to-[var(--intel-teal)] text-sm font-bold text-white shadow-[var(--shadow-sm)]"
        >
          S
        </span>
        <div className="leading-tight">
          <div className="text-[13px] font-bold tracking-wide">Stock Agent</div>
          <div className="text-[10px] text-[var(--color-text-faint)]">Research · Sectors · Portfolios</div>
        </div>
      </NavLink>

      <nav className="flex flex-col gap-0.5">
        {NAV_ITEMS.map((item) => {
          if (item.requiresAuth && status !== 'authenticated') {
            return (
              <span
                key={item.label}
                title="Sign in required"
                aria-disabled="true"
                className="flex cursor-not-allowed items-center gap-2.5 rounded-[var(--radius-md)] px-3 py-2 text-left text-[13px] font-medium text-[var(--color-text-faint)]/60"
              >
                <Icon path={item.icon} className="h-4 w-4 shrink-0" />
                <span className="flex-1">{item.label}</span>
                <Icon path={ICON.lock} className="h-3 w-3 shrink-0" />
              </span>
            )
          }
          return (
            <NavLink
              key={item.label}
              to={item.to}
              end={item.to === paths.home()}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-[var(--radius-md)] px-3 py-2 text-left text-[13px] font-medium transition-colors ${
                  isActive
                    ? 'bg-[var(--color-accent-soft)] text-[var(--color-text)]'
                    : 'text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]'
                }`
              }
            >
              <Icon path={item.icon} className="h-4 w-4 shrink-0" />
              <span className="flex-1">{item.label}</span>
            </NavLink>
          )
        })}
        {UPCOMING.map((label) => (
          <span
            key={label}
            title="Coming soon"
            aria-disabled="true"
            className="flex cursor-not-allowed items-center gap-2.5 rounded-[var(--radius-md)] px-3 py-2 text-left text-[13px] font-medium text-[var(--color-text-faint)]/60"
          >
            <Icon path={ICON.lock} className="h-4 w-4 shrink-0" />
            <span className="flex-1">{label}</span>
          </span>
        ))}
      </nav>
    </aside>
  )
}
