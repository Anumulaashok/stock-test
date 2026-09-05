import { Outlet } from 'react-router-dom'
import { SideNav } from './SideNav'
import { TopBar } from './TopBar'
import { StickyAskAssistant } from '../components/StickyAskAssistant'
import { CommandPalette } from '../features/commandPalette/CommandPalette'
import { MobileNavDrawer } from './MobileNavDrawer'
import { DataSourceStatusProvider } from '../dataSources/DataSourceStatusContext'
import { useCurrentTicker } from '../hooks/useCurrentTicker'

/**
 * The one app shell -- replaces the two competing nav shells that used
 * to exist (`App.tsx`'s top header and `IntelligencePage`'s own
 * sidebar/topbar). `.app-shell-bg` is the renamed `.intel-theme`: it was
 * always just a background layer over the shared design tokens, not a
 * separate theme, so it now covers the whole app instead of one page.
 */
export function AppShell() {
  const currentTicker = useCurrentTicker()

  return (
    <DataSourceStatusProvider>
      <div className="app-shell-bg flex min-h-screen text-[var(--color-text)]">
        <SideNav />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <div className="min-w-0 flex-1">
            <Outlet />
          </div>
        </div>
        <StickyAskAssistant ticker={currentTicker} />
        <CommandPalette />
        <MobileNavDrawer />
      </div>
    </DataSourceStatusProvider>
  )
}
