import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchAlertTriggers } from '../api/alerts'
import { Icon, ICON } from '../components/ui/Icon'
import { paths } from '../routes/paths'
import { useAuth } from '../auth/AuthContext'

/**
 * Unread count only -- a cheap DB-only read of already-recorded
 * triggers (`GET /alerts/triggers?unacknowledged_only=true`), never a
 * live re-check of conditions (that's `POST /alerts/evaluate`, only
 * run when the Alerts page itself opens; see AlertsPage.tsx and D6).
 * Fetched once per app load, not on a timer -- this bell does not
 * imply background monitoring.
 */
export function AlertsBell() {
  const { status } = useAuth()
  const navigate = useNavigate()
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    if (status !== 'authenticated') {
      setCount(null)
      return
    }
    let cancelled = false
    fetchAlertTriggers(true)
      .then((triggers) => {
        if (!cancelled) setCount(triggers.length)
      })
      .catch(() => {
        if (!cancelled) setCount(null)
      })
    return () => {
      cancelled = true
    }
  }, [status])

  if (status !== 'authenticated') {
    return (
      <button
        type="button"
        title="Notifications (sign in to use alerts)"
        disabled
        className="flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-border)] text-[var(--color-text-faint)]"
      >
        <Icon path={ICON.bell} className="h-4 w-4" />
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={() => navigate(paths.alerts())}
      title={count ? `${count} unacknowledged alert${count === 1 ? '' : 's'}` : 'Alerts'}
      className="relative flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-border)] text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
    >
      <Icon path={ICON.bell} className="h-4 w-4" />
      {count !== null && count > 0 && (
        <span
          aria-live="polite"
          className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--color-status-negative)] px-1 text-[10px] font-bold text-white"
        >
          {count > 9 ? '9+' : count}
        </span>
      )}
      <span className="sr-only" aria-live="polite">
        {count !== null && count > 0 ? `${count} unacknowledged alert${count === 1 ? '' : 's'}` : ''}
      </span>
    </button>
  )
}
