import { useState } from 'react'
import { fetchMarketOpportunity } from '../../api/sectors'
import { useAsync } from '../../hooks/useAsync'
import { AsyncSection } from '../../components/ui/AsyncSection'
import { Skeleton } from '../../components/ui/Skeleton'
import { formatDateTime } from '../../lib/format'
import { SectorCard } from './SectorCard'
import { SectorStockTable } from './SectorStockTable'

function SectorGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" aria-hidden="true">
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} className="h-40 w-full" />
      ))}
    </div>
  )
}

/**
 * "Market Opportunity" -- sector ranking built entirely from the app's
 * own deterministic per-ticker scoring (see app/sectors/service.py).
 * Consolidates the two previous duplicate implementations
 * (`SectorOverview` and `IntelligencePage`'s `MarketOpportunitySection`)
 * into one real page, routed at `/discover`.
 */
export function MarketOpportunity() {
  const [refreshToken, setRefreshToken] = useState(0)
  const [selectedSector, setSelectedSector] = useState<string | null>(null)
  const state = useAsync(() => fetchMarketOpportunity(refreshToken > 0), [refreshToken])
  const refreshing = state.status === 'loading' && refreshToken > 0

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[length:var(--text-page-title)] font-bold leading-tight tracking-tight text-[var(--color-text)]">
            Discover
          </h1>
          <p className="support-text">Sectors ranked by average deterministic score across curated constituents.</p>
        </div>
        <button
          type="button"
          onClick={() => setRefreshToken((n) => n + 1)}
          disabled={state.status === 'loading'}
          className="btn-secondary shrink-0 px-3 py-1.5 text-xs"
        >
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </header>

      <AsyncSection
        state={state}
        onRetry={state.reload}
        errorTitle="Could not load sector rankings"
        skeleton={<SectorGridSkeleton />}
      >
        {(data) => {
          if (data.status === 'unavailable' || data.sectors.length === 0) {
            return (
              <p className="surface-card p-4 text-sm support-text">
                Sector ranking is unavailable — configure a financial data provider to enable it.
              </p>
            )
          }

          const selected = data.sectors.find((s) => s.sector === selectedSector) ?? data.sectors[0]
          const updated = formatDateTime(data.generated_at)

          return (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--color-text-faint)]">
                {updated && <span>Updated {updated}</span>}
                {data.status === 'partial' && (
                  <span className="text-[var(--color-status-medium)]">Some sectors could not be fully scored.</span>
                )}
              </div>

              {data.warnings.length > 0 && (
                <ul className="surface-card flex flex-col gap-1 p-3 text-xs text-[var(--color-text-faint)]">
                  {data.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              )}

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {data.sectors.map((sector, i) => (
                  <SectorCard
                    key={sector.sector}
                    sector={sector}
                    rank={i + 1}
                    selected={sector.sector === selected.sector}
                    onSelect={() => setSelectedSector(sector.sector)}
                  />
                ))}
              </div>

              <SectorStockTable sector={selected} />
            </>
          )
        }}
      </AsyncSection>
    </main>
  )
}
