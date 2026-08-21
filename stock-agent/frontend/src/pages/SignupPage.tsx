import { useState, type FormEvent } from 'react'
import { useAuth } from '../auth/AuthContext'
import { ApiError } from '../api/client'

export function SignupPage({ onSuccess, onNavigateToLogin }: { onSuccess: () => void; onNavigateToLogin: () => void }) {
  const { signup } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await signup(email, password)
      onSuccess()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto flex max-w-sm flex-col gap-6 px-4 py-16">
      <div>
        <h1 className="text-xl font-semibold">Create an account</h1>
        <p className="text-sm text-[var(--color-text-faint)]">Track a portfolio and watchlist.</p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-3 py-2 text-[var(--color-text)] focus:border-[var(--color-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-3 py-2 text-[var(--color-text)] focus:border-[var(--color-accent)]"
          />
          <span className="text-xs text-[var(--color-text-faint)]">At least 8 characters.</span>
        </label>

        {error && (
          <p role="alert" className="text-sm text-[var(--color-status-negative)]">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-[var(--color-accent)] px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? 'Creating account…' : 'Sign up'}
        </button>
      </form>

      <p className="text-sm text-[var(--color-text-faint)]">
        Already have an account?{' '}
        <button type="button" onClick={onNavigateToLogin} className="text-[var(--color-accent)] underline">
          Log in
        </button>
      </p>
    </main>
  )
}
