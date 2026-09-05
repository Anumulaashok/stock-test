import { NavLink } from 'react-router-dom'
import { paths } from '../routes/paths'
import { NavLinks } from './NavLinks'
import { SideNavHealthBadge } from './SideNavHealthBadge'

function Logo({ withLabel }: { withLabel: boolean }) {
  return (
    <NavLink to={paths.home()} className="flex items-center gap-2 px-1 text-left">
      <span
        aria-hidden="true"
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-gradient-to-br from-[var(--intel-violet)] to-[var(--intel-teal)] text-sm font-bold text-white shadow-[var(--shadow-sm)]"
      >
        S
      </span>
      {withLabel && (
        <div className="leading-tight">
          <div className="text-[13px] font-bold tracking-wide">Stock Agent</div>
          <div className="text-[10px] text-[var(--color-text-faint)]">Research · Sectors · Portfolios</div>
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
 */
export function SideNav() {
  return (
    <>
      <aside className="hidden w-60 shrink-0 flex-col gap-6 border-r border-[var(--color-border)] px-4 py-6 lg:flex">
        <Logo withLabel />
        <NavLinks variant="full" />
        <div className="mt-auto">
          <SideNavHealthBadge />
        </div>
      </aside>

      <aside className="hidden w-16 shrink-0 flex-col items-center gap-6 border-r border-[var(--color-border)] px-2 py-6 md:flex lg:hidden">
        <Logo withLabel={false} />
        <NavLinks variant="icon" />
      </aside>
    </>
  )
}
