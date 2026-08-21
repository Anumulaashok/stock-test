import { useState } from 'react'
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

export default function App() {
  const { status, user, logout } = useAuth()
  const [view, setView] = useState<View>({ kind: 'analysis' })

  async function handleLogout() {
    await logout()
    setView({ kind: 'analysis' })
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="font-mono-nums text-sm font-semibold tracking-wide">STOCK-AGENT</span>
            <nav className="flex gap-4 text-sm">
              <button
                type="button"
                onClick={() => setView({ kind: 'analysis' })}
                className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              >
                Research
              </button>
              {status === 'authenticated' && (
                <button
                  type="button"
                  onClick={() => setView({ kind: 'dashboard' })}
                  className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                >
                  Dashboard
                </button>
              )}
            </nav>
          </div>

          <div className="flex items-center gap-3 text-xs">
            {status === 'authenticated' && (
              <>
                <span className="text-[var(--color-text-faint)]">{user?.email}</span>
                <button type="button" onClick={handleLogout} className="text-[var(--color-accent)] underline">
                  Log out
                </button>
              </>
            )}
            {status === 'anonymous' && (
              <>
                <button type="button" onClick={() => setView({ kind: 'login' })} className="text-[var(--color-accent)] underline">
                  Log in
                </button>
                <button type="button" onClick={() => setView({ kind: 'signup' })} className="text-[var(--color-accent)] underline">
                  Sign up
                </button>
              </>
            )}
          </div>
        </div>
      </header>

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
  )
}
