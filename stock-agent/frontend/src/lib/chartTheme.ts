const FALLBACKS: Record<
  'grid' | 'tick' | 'historical' | 'predicted' | 'predictedFill' | 'bandFill' | 'volumeBar' | 'pointBorder' | 'quadrantLine',
  string
> = {
  grid: 'rgba(148, 163, 184, 0.15)',
  tick: '#9aa5c7',
  historical: '#9ca3af',
  predicted: '#2952a3',
  predictedFill: 'rgba(41, 82, 163, 0.15)',
  bandFill: 'rgba(41, 82, 163, 0.12)',
  volumeBar: 'rgba(148, 163, 184, 0.45)',
  pointBorder: 'rgba(255, 255, 255, 0.5)',
  quadrantLine: 'rgba(148, 163, 184, 0.55)',
}

export type ChartColors = typeof FALLBACKS

function readVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

/**
 * Chart.js reads plain color strings at canvas-build time -- it does
 * not understand CSS custom properties and never re-reads the page's
 * CSS on a theme change (D8). Call this fresh inside the effect that
 * builds/rebuilds a chart (with `theme` in that effect's dependency
 * array), never once at module load.
 */
export function readChartColors(): ChartColors {
  return {
    grid: readVar('--chart-grid', FALLBACKS.grid),
    tick: readVar('--chart-tick', FALLBACKS.tick),
    historical: readVar('--chart-historical', FALLBACKS.historical),
    predicted: readVar('--chart-predicted', FALLBACKS.predicted),
    predictedFill: readVar('--chart-predicted-fill', FALLBACKS.predictedFill),
    bandFill: readVar('--chart-band-fill', FALLBACKS.bandFill),
    volumeBar: readVar('--chart-volume-bar', FALLBACKS.volumeBar),
    pointBorder: readVar('--chart-point-border', FALLBACKS.pointBorder),
    quadrantLine: readVar('--chart-quadrant-line', FALLBACKS.quadrantLine),
  }
}
