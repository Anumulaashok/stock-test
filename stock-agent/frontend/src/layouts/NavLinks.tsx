import { NavLink } from 'react-router-dom'
import { paths } from '../routes/paths'
import { Icon, ICON } from '../components/ui/Icon'
import { useAuth } from '../auth/AuthContext'
import { NAV_ITEMS, NAV_UPCOMING } from './navItems'

/**
 * The shared nav-item list -- used by the full sidebar (`lg+`), the
 * icon-only rail (`md`-`lg`), and the mobile drawer (below `md`). One
 * source of truth for the item list/auth-gating logic instead of three
 * copies drifting apart.
 */
export function NavLinks({ variant, onNavigate }: { variant: 'full' | 'icon'; onNavigate?: () => void }) {
  const { status } = useAuth()
  const showLabel = variant === 'full'

  return (
    <nav className={`flex flex-col gap-0.5 ${variant === 'icon' ? 'items-center' : ''}`}>
      {NAV_ITEMS.map((item) => {
        if (item.requiresAuth && status !== 'authenticated') {
          return (
            <span
              key={item.label}
              title="Sign in required"
              aria-disabled="true"
              className={`flex cursor-not-allowed items-center gap-2.5 rounded-[var(--radius-md)] px-3 py-2 text-left text-[13px] font-medium text-[var(--color-text-faint)]/60 ${
                variant === 'icon' ? 'justify-center px-2.5' : ''
              }`}
            >
              <Icon path={item.icon} className="h-4 w-4 shrink-0" />
              {showLabel && <span className="flex-1">{item.label}</span>}
              {showLabel && <Icon path={ICON.lock} className="h-3 w-3 shrink-0" />}
            </span>
          )
        }
        return (
          <NavLink
            key={item.label}
            to={item.to}
            end={item.to === paths.home()}
            onClick={onNavigate}
            title={variant === 'icon' ? item.label : undefined}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-[var(--radius-md)] px-3 py-2 text-left text-[13px] font-medium transition-colors ${
                variant === 'icon' ? 'justify-center px-2.5' : ''
              } ${
                isActive
                  ? 'bg-[var(--color-accent-soft)] text-[var(--color-text)]'
                  : 'text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]'
              }`
            }
          >
            <Icon path={item.icon} className="h-4 w-4 shrink-0" />
            {showLabel && <span className="flex-1">{item.label}</span>}
          </NavLink>
        )
      })}
      {NAV_UPCOMING.map((label) => (
        <span
          key={label}
          title="Coming soon"
          aria-disabled="true"
          className={`flex cursor-not-allowed items-center gap-2.5 rounded-[var(--radius-md)] px-3 py-2 text-left text-[13px] font-medium text-[var(--color-text-faint)]/60 ${
            variant === 'icon' ? 'justify-center px-2.5' : ''
          }`}
        >
          <Icon path={ICON.lock} className="h-4 w-4 shrink-0" />
          {showLabel && <span className="flex-1">{label}</span>}
        </span>
      ))}
    </nav>
  )
}
