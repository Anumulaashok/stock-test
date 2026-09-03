import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { SearchBar } from '../components/SearchBar'
import { Icon, ICON } from '../components/ui/Icon'
import { paths } from '../routes/paths'
import { Breadcrumbs } from './Breadcrumbs'

export function TopBar() {
  const { status, user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <header className="flex flex-col gap-2 border-b border-[var(--color-border)] px-5 py-3.5">
      <div className="flex flex-wrap items-center gap-3 sm:gap-4">
        <div className="min-w-0 flex-1">
          <SearchBar onSubmit={(ticker) => navigate(paths.stock(ticker.trim().toUpperCase()))} disabled={false} />
        </div>
        <div className="flex items-center gap-3 text-right text-sm">
          <button
            type="button"
            title="Notifications (coming soon)"
            disabled
            className="flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-border)] text-[var(--color-text-faint)]"
          >
            <Icon path={ICON.bell} className="h-4 w-4" />
          </button>
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
