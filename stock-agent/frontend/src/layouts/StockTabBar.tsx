import { NavLink, useLocation } from 'react-router-dom'
import { paths, STOCK_TABS } from '../routes/paths'

/**
 * Eight links, not ARIA tabs -- these are real routes with their own
 * URLs, so `<nav>` + `aria-current="page"` is the correct semantic, not
 * `role="tablist"`. Each link carries the current `?run=` search param
 * forward, or switching tabs while viewing a historical snapshot would
 * silently drop back to the latest one.
 */
export function StockTabBar({ ticker }: { ticker: string }) {
  const location = useLocation()

  return (
    <nav aria-label="Stock sections" className="flex gap-1 overflow-x-auto border-b border-[var(--color-border)]">
      {STOCK_TABS.map((tab) => (
        <NavLink
          key={tab.segment}
          to={{ pathname: paths.stockTab(ticker, tab.segment), search: location.search }}
          end={tab.segment === ''}
          className={({ isActive }) =>
            `shrink-0 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
              isActive
                ? 'border-[var(--color-accent)] text-[var(--color-text)]'
                : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            }`
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}
