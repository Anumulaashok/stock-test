export type HeatBand = 'strong' | 'neutral' | 'weak' | 'unavailable'

export const HEAT_BAND_LABEL: Record<HeatBand, string> = {
  strong: 'Strong (70+)',
  neutral: 'Neutral (45-69)',
  weak: 'Weak (<45)',
  unavailable: 'Unavailable',
}

export const HEAT_BAND_COLOR: Record<HeatBand, string> = {
  strong: 'var(--color-status-positive)',
  neutral: 'var(--color-status-medium)',
  weak: 'var(--color-status-negative)',
  unavailable: 'var(--color-border)',
}

/** Buckets an already-computed sector score into a display color tier --
 * a categorization of a known value, not a new statistic (I2). */
export function sectorHeatBand(score: string | null): HeatBand {
  if (score === null) return 'unavailable'
  const parsed = Number(score)
  if (!Number.isFinite(parsed)) return 'unavailable'
  if (parsed >= 70) return 'strong'
  if (parsed >= 45) return 'neutral'
  return 'weak'
}
