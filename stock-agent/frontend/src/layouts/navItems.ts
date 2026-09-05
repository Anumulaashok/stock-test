import { paths } from '../routes/paths'
import { ICON } from '../components/ui/Icon'

export const NAV_ITEMS: { label: string; icon: string; to: string; requiresAuth?: boolean }[] = [
  { label: 'Intelligence', icon: ICON.core, to: paths.home() },
  { label: 'Discover', icon: ICON.sectors, to: paths.discover() },
  { label: 'Screener', icon: ICON.screener, to: paths.screener() },
  { label: 'Watchlist', icon: ICON.watchlist, to: paths.watchlist(), requiresAuth: true },
  { label: 'Portfolio', icon: ICON.portfolio, to: paths.portfolio(), requiresAuth: true },
  { label: 'Alerts', icon: ICON.bell, to: paths.alerts(), requiresAuth: true },
  { label: 'Research', icon: ICON.archive, to: paths.research() },
  { label: 'Settings', icon: ICON.settings, to: paths.settings(), requiresAuth: true },
]

/** Not-yet-built roadmap items, shown locked so the roadmap stays
 * visible without linking anywhere. */
export const NAV_UPCOMING = ['News']
