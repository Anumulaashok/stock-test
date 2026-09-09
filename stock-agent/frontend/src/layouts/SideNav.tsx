import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { paths } from '../routes/paths'
import { NavLinks } from './NavLinks'
import { SideNavHealthBadge } from './SideNavHealthBadge'
import { Icon, ICON } from '../components/ui/Icon'

const COLLAPSE_STORAGE_KEY = 'stock-agent-sidenav-collapsed'

function readStoredCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function Logo({ withLabel }: { withLabel: boolean }) {
  return (
    <NavLink to={paths.home()} className="flex items-center gap-2.5 px-1 text-left">
      <span
        aria-hidden="true"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] bg-[var(--color-text)] text-xs font-extrabold text-[var(--color-bg)]"
      >
        S
      </span>
      {withLabel && (
        <div className="min-w-0 leading-tight">
          <div className="truncate text-[13px] font-bold tracking-wide">Stock Agent</div>
          <div className="truncate text-[10px] text-[var(--color-text-faint)]">Research · Sectors · Portfolios</div>
        </div>
      )}
    </NavLink>
  )
}

/**
 * Three responsive layers of the same nav (Wave 7 responsive pass --
 * `lg+` full sidebar, `md`-`lg` icon-only rail, below `md` a drawer via
 * `MobileNavDrawer` triggered from `TopBar`'s hamburger button). Only
 * one is visible at a time; `NavLinks` is the shared item list so all
 * three stay in sync.
 *
 * On `lg+` the full sidebar can also be manually collapsed to the same
 * icon-only width as the `md`-`lg` rail -- a per-viewer preference
 * (persisted like the theme toggle), not tied to viewport size.
 */
export function SideNav() {
  const [collapsed, setCollapsed] = useState(readStoredCollapsed)

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_STORAGE_KEY, collapsed ? '1' : '0')
    } catch {
      // Best-effort persistence -- a private-browsing block shouldn't break the toggle.
    }
  }, [collapsed])

  return (
    <>
      <aside
        className={`hidden shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-subtle)] py-4 transition-[width] duration-150 lg:flex ${
          collapsed ? 'w-16 items-center px-2' : 'w-60 px-3'
        }`}
      >
        <div className={`flex items-center gap-2 px-1 pb-4 ${collapsed ? 'flex-col' : 'justify-between'}`}>
          <Logo withLabel={!collapsed} />
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--radius-sm)] text-[var(--color-text-faint)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
          >
            <Icon path={collapsed ? ICON.chevronRight : ICON.chevronLeft} className="h-3.5 w-3.5" />
          </button>
        </div>
        <NavLinks variant={collapsed ? 'icon' : 'full'} />
        <div className="mt-auto w-full pt-4">{!collapsed && <SideNavHealthBadge />}</div>
      </aside>

      <aside className="hidden w-16 shrink-0 flex-col items-center gap-6 border-r border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2 py-6 md:flex lg:hidden">
        <Logo withLabel={false} />
        <NavLinks variant="icon" />
      </aside>
    </>
  )
}
