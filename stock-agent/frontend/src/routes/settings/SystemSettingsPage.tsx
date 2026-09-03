import { HistoricalImportCard } from '../../features/settings/HistoricalImportCard'
import { MappingImportCard } from '../../features/settings/MappingImportCard'
import { ScreenerCookieCard } from '../../features/settings/ScreenerCookieCard'

/** Admin/operator widgets evicted from `IntelligencePage` -- data
 * backfill and source-credential management. Never renders a key,
 * cookie, or token, only status words. */
export function SystemSettingsPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-base font-semibold">System</h2>
        <p className="support-text">Data backfill and source-credential administration.</p>
      </div>
      <ScreenerCookieCard />
      <HistoricalImportCard />
      <MappingImportCard />
    </div>
  )
}
