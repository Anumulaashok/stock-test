import { useState, type ReactNode } from 'react'
import { AnalysisPage } from './pages/AnalysisPage'
import { LoginPage } from './pages/LoginPage'
import { SignupPage } from './pages/SignupPage'
import { DashboardPage } from './pages/DashboardPage'
import { useAuth } from './auth/AuthContext'

type View =
  | { kind: 'analysis'; ticker?: string }
  | { kind: 'dashboard' }
  | { kind: 'login' }
  | { kind: 'signup' }

function NavLink({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative px-1 py-1.5 text-sm font-medium transition-colors ${
        active ? 'text-[var(--color-text)]' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
      }`}
    >
      {children}
      <span
        className={`absolute -bottom-[1px] left-0 h-[2px] w-full rounded-full bg-[var(--color-accent)] transition-transform duration-200 ${
          active ? 'scale-x-100' : 'scale-x-0'
        }`}
        aria-hidden="true"
      />
    </button>
  )
}

function LockIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-3 w-3">
      <rect x="5" y="9" width="10" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M7 9V6.5a3 3 0 0 1 6 0V9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

/** Features that aren't built yet -- shown in the nav so the roadmap is
 * visible, but locked (not clickable) rather than linking to nothing.
 * Forecasting and Ask AI both shipped as sections of the Research report
 * (see `ForecastSection`/`AskAssistantSection`), so they have their own
 * real `NavLink`s below instead of appearing here. */
const UPCOMING_TABS = ['Screener', 'Alerts', 'News'] as const

/** Scrolling delay after switching to the analysis view, so the target
 * section has mounted before we try to find it in the DOM. */
const SCROLL_TO_SECTION_DELAY_MS = 50

function LockedNavLink({ children }: { children: ReactNode }) {
  return (
    <span
      title="Coming soon"
      aria-disabled="true"
      className="inline-flex cursor-not-allowed select-none items-center gap-1.5 px-1 py-1.5 text-sm font-medium text-[var(--color-text-faint)]/70"
    >
      {children}
      <LockIcon />
    </span>
  )
}

export default function App() {
  const { status, user, logout } = useAuth()
  const [view, setView] = useState<View>({ kind: 'analysis' })

  async function handleLogout() {
    await logout()
    setView({ kind: 'analysis' })
  }

  /** Forecasting isn't a separate page -- it's the `ForecastSection` of
   * the Research report -- so the nav link switches to the analysis
   * view (a no-op if already there) and scrolls it into view rather
   * than routing anywhere. If no report has a forecast yet (nothing
   * analyzed, or the ticker has no forecastable data), the section
   * simply isn't in the DOM and this is a no-op landing on Research. */
  function goToSection(headingId: string) {
    setView({ kind: 'analysis' })
    window.setTimeout(() => {
      document.getElementById(headingId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, SCROLL_TO_SECTION_DELAY_MS)
  }

  return (
    <div className="min-h-screen text-[var(--color-text)]">
      <header className="sticky top-0 z-20 border-b border-[var(--color-border)] bg-[var(--color-surface)]/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3.5 sm:px-6">
          <div className="flex min-w-0 flex-1 items-center gap-4 sm:gap-8">
            <div className="flex shrink-0 items-center gap-2">
              <span
                aria-hidden="true"
                className="flex h-7 w-7 items-center justify-center rounded-[8px] bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-strong)] text-[13px] font-bold text-white shadow-[var(--shadow-sm)]"
              >
                S
              </span>
              <span className="hidden font-mono-nums text-[13px] font-bold tracking-[0.08em] text-[var(--color-text)] sm:inline">
                STOCK-AGENT
              </span>
            </div>
            <nav className="flex min-w-0 flex-1 items-center gap-4 overflow-x-auto sm:gap-6">
              <NavLink active={view.kind === 'analysis'} onClick={() => setView({ kind: 'analysis' })}>
                Research
              </NavLink>
              {status === 'authenticated' && (
                <NavLink active={view.kind === 'dashboard'} onClick={() => setView({ kind: 'dashboard' })}>
                  Dashboard
                </NavLink>
              )}
              <span aria-hidden="true" className="h-4 w-px shrink-0 bg-[var(--color-border)]" />
              <NavLink active={false} onClick={() => goToSection('forecast-heading')}>
                Forecasting
              </NavLink>
              <NavLink active={false} onClick={() => goToSection('ask-assistant-heading')}>
                Ask AI
              </NavLink>
              {UPCOMING_TABS.map((tab) => (
                <LockedNavLink key={tab}>{tab}</LockedNavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-3 text-sm">
            {status === 'authenticated' && (
              <>
                <span className="hidden text-[var(--color-text-faint)] sm:inline">{user?.email}</span>
                <button
                  type="button"
                  onClick={handleLogout}
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
                  onClick={() => setView({ kind: 'login' })}
                  className="px-2 py-1.5 font-medium text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)]"
                >
                  Log in
                </button>
                <button
                  type="button"
                  onClick={() => setView({ kind: 'signup' })}
                  className="btn-primary px-3.5 py-1.5 text-sm"
                >
                  Sign up
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      <div key={view.kind} className="animate-fade-in-up">
        {view.kind === 'analysis' && <AnalysisPage initialTicker={view.ticker} />}
        {view.kind === 'dashboard' && status === 'authenticated' && (
          <DashboardPage onAnalyze={(ticker) => setView({ kind: 'analysis', ticker })} />
        )}
        {view.kind === 'login' && (
          <LoginPage
            onSuccess={() => setView({ kind: 'dashboard' })}
            onNavigateToSignup={() => setView({ kind: 'signup' })}
          />
        )}
        {view.kind === 'signup' && (
          <SignupPage
            onSuccess={() => setView({ kind: 'dashboard' })}
            onNavigateToLogin={() => setView({ kind: 'login' })}
          />
        )}
      </div>
    </div>
  )
}
