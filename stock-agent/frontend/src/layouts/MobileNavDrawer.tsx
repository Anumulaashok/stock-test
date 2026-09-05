import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { paths } from '../routes/paths'
import { NavLinks } from './NavLinks'
import { SideNavHealthBadge } from './SideNavHealthBadge'

export const OPEN_MOBILE_NAV_EVENT = 'open-mobile-nav'

/**
 * Below `md`, `SideNav` renders nothing (the full sidebar and icon
 * rail are both `md+`-only) -- this drawer is the only way to reach
 * navigation on a small screen. Same open/close-by-event pattern as
 * `CommandPalette`, so `TopBar`'s hamburger button doesn't need to
 * lift shared state up through `AppShell`.
 */
export function MobileNavDrawer() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    function handleOpenEvent() {
      setOpen(true)
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener(OPEN_MOBILE_NAV_EVENT, handleOpenEvent)
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener(OPEN_MOBILE_NAV_EVENT, handleOpenEvent)
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex md:hidden" onClick={() => setOpen(false)}>
      <div className="absolute inset-0 bg-black/50" aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        onClick={(e) => e.stopPropagation()}
        className="relative flex w-64 max-w-[80vw] flex-col gap-6 border-r border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-6 shadow-[var(--shadow-lg)]"
      >
        <NavLink to={paths.home()} onClick={() => setOpen(false)} className="flex items-center gap-2 px-1 text-left">
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

        <NavLinks variant="full" onNavigate={() => setOpen(false)} />

        <div className="mt-auto">
          <SideNavHealthBadge />
        </div>
      </div>
    </div>
  )
}
