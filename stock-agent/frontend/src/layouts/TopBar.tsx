import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Icon, ICON } from '../components/ui/Icon'
import { SearchBar } from '../components/SearchBar'
import { ThemeToggle } from '../components/ThemeToggle'
import { OPEN_COMMAND_PALETTE_EVENT } from '../features/commandPalette/CommandPalette'
import { OPEN_MOBILE_NAV_EVENT } from './MobileNavDrawer'
import { paths } from '../routes/paths'
import { Breadcrumbs } from './Breadcrumbs'
import { AlertsBell } from './AlertsBell'

export function TopBar() {
  const { status, user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <header className="flex flex-col gap-2 border-b border-[var(--color-border)] px-5 py-3.5">
      <div className="flex flex-wrap items-center gap-3 sm:gap-4">
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event(OPEN_MOBILE_NAV_EVENT))}
          className="flex shrink-0 items-center justify-center rounded-[var(--radius-sm)] border border-[var(--color-border)] p-2 text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)] md:hidden"
        >
          <Icon path={ICON.menu} className="h-4.5 w-4.5" />
          <span className="sr-only">Open navigation</span>
        </button>
        <div className="min-w-0 flex-1">
          <SearchBar onSubmit={(ticker) => navigate(paths.stock(ticker.trim().toUpperCase()))} disabled={false} />
        </div>
        <div className="flex items-center gap-3 text-right text-sm">
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event(OPEN_COMMAND_PALETTE_EVENT))}
            title="Command palette"
            className="hidden items-center gap-1 rounded-[var(--radius-sm)] border border-[var(--color-border)] px-2.5 py-1.5 font-mono-nums text-xs text-[var(--color-text-faint)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)] sm:flex"
          >
            <span aria-hidden="true">⌘K</span>
            <span className="sr-only">Open command palette</span>
          </button>
          <ThemeToggle />
          <AlertsBell />
          {status === 'authenticated' && (
            <>
              <span className="hidden text-[var(--color-text-faint)] md:inline">{user?.email}</span>
              <button
                type="button"
                onClick={() => void logout()}
                className="rounded-[var(--radius-sm)] border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
              >
                Log out
              </button>
            </>
          )}
          {status === 'anonymous' && (
            <>
              <button
                type="button"
                onClick={() => navigate(paths.login())}
                className="px-2 py-1.5 font-medium text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)]"
              >
                Log in
              </button>
              <button type="button" onClick={() => navigate(paths.signup())} className="btn-primary px-3.5 py-1.5 text-sm">
                Sign up
              </button>
            </>
          )}
        </div>
      </div>
      <Breadcrumbs />
    </header>
  )
}
