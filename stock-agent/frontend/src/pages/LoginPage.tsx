import { useState, type FormEvent } from 'react'
import { useAuth } from '../auth/AuthContext'
import { ApiError } from '../api/client'

export function LoginPage({ onSuccess, onNavigateToSignup }: { onSuccess: () => void; onNavigateToSignup: () => void }) {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      onSuccess()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-58px)] max-w-sm flex-col justify-center px-4 py-12">
      <div className="animate-fade-in-up surface-card p-8">
        <div className="mb-7 flex flex-col items-center text-center">
          <span
            aria-hidden="true"
            className="mb-4 flex h-11 w-11 items-center justify-center rounded-[10px] bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-strong)] text-lg font-bold text-white shadow-[var(--shadow-sm)]"
          >
            S
          </span>
          <h1 className="text-xl font-semibold">Welcome back</h1>
          <p className="mt-1 text-sm text-[var(--color-text-faint)]">Log in to access your portfolio and watchlist.</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-[var(--color-text-muted)]">
            Email
            <input
              type="email"
              required
              autoFocus
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field px-3.5 py-2.5 text-[var(--color-text)]"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-[var(--color-text-muted)]">
            Password
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field px-3.5 py-2.5 text-[var(--color-text)]"
            />
          </label>

          {error && (
            <p
              role="alert"
              className="rounded-[var(--radius-sm)] border border-[var(--color-status-negative)]/25 bg-[var(--color-status-negative)]/8 px-3 py-2 text-sm text-[var(--color-status-negative)]"
            >
              {error}
            </p>
          )}

          <button type="submit" disabled={submitting} className="btn-primary mt-1 px-4 py-2.5">
            {submitting && (
              <span
                aria-hidden="true"
                className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white"
              />
            )}
            {submitting ? 'Logging in…' : 'Log in'}
          </button>
        </form>
      </div>

      <p className="mt-5 text-center text-sm text-[var(--color-text-faint)]">
        No account?{' '}
        <button
          type="button"
          onClick={onNavigateToSignup}
          className="font-medium text-[var(--color-accent)] underline-offset-2 hover:underline"
        >
          Sign up
        </button>
      </p>
    </main>
  )
}
