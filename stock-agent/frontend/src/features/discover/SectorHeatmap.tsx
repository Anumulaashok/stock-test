import { useState, type KeyboardEvent } from 'react'
import type { SectorSummary } from '../../types/backend'
import { scoreText } from './scoreDisplay'
import { HEAT_BAND_COLOR, HEAT_BAND_LABEL, sectorHeatBand, type HeatBand } from './sectorHeatBand'

const ALL_BANDS: HeatBand[] = ['strong', 'neutral', 'weak', 'unavailable']

/**
 * Sector tiles colored by score band -- color is never the only
 * channel (G8): each tile also shows the real score number, and the
 * legend spells out what each color means. Arrow-key traversable via a
 * roving tabindex (one tile in the tab order at a time).
 */
export function SectorHeatmap({
  sectors,
  selectedSector,
  onSelect,
}: {
  sectors: SectorSummary[]
  selectedSector: string
  onSelect: (sector: string) => void
}) {
  const [focusedIndex, setFocusedIndex] = useState(() => Math.max(0, sectors.findIndex((s) => s.sector === selectedSector)))

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number | null = null
    if (event.key === 'ArrowRight') next = (index + 1) % sectors.length
    else if (event.key === 'ArrowLeft') next = (index - 1 + sectors.length) % sectors.length
    else if (event.key === 'ArrowDown') next = Math.min(index + 4, sectors.length - 1)
    else if (event.key === 'ArrowUp') next = Math.max(index - 4, 0)
    if (next === null) return
    event.preventDefault()
    setFocusedIndex(next)
    document.getElementById(`sector-tile-${next}`)?.focus()
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        role="grid"
        aria-label="Sector heatmap"
        className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6"
      >
        {sectors.map((sector, index) => {
          const band = sectorHeatBand(sector.sector_score)
          const selected = sector.sector === selectedSector
          return (
            <button
              key={sector.sector}
              id={`sector-tile-${index}`}
              type="button"
              role="gridcell"
              tabIndex={index === focusedIndex ? 0 : -1}
              onFocus={() => setFocusedIndex(index)}
              onKeyDown={(e) => handleKeyDown(e, index)}
              onClick={() => onSelect(sector.sector)}
              aria-pressed={selected}
              aria-label={`${sector.sector}, score ${scoreText(sector.sector_score)}, ${HEAT_BAND_LABEL[band]}`}
              className={`flex aspect-square flex-col items-center justify-center gap-1 rounded-[var(--radius-sm)] border-2 p-2 text-center transition-transform ${
                selected ? 'border-[var(--color-text)]' : 'border-transparent'
              }`}
              style={{ background: `color-mix(in srgb, ${HEAT_BAND_COLOR[band]} 28%, var(--color-bg-subtle))` }}
            >
              <span className="truncate text-[11px] font-semibold text-[var(--color-text)]">{sector.sector}</span>
              <span className="font-mono-nums text-lg font-bold text-[var(--color-text)]">{scoreText(sector.sector_score)}</span>
            </button>
          )
        })}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--color-text-faint)]">
        <span className="metric-label">Legend</span>
        {ALL_BANDS.map((band) => (
          <span key={band} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="h-3 w-3 rounded-sm"
              style={{ background: `color-mix(in srgb, ${HEAT_BAND_COLOR[band]} 28%, var(--color-bg-subtle))`, border: `1px solid ${HEAT_BAND_COLOR[band]}` }}
            />
            {HEAT_BAND_LABEL[band]}
          </span>
        ))}
      </div>
    </div>
  )
}
