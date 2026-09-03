import type { ScoreBand, Severity } from '../types/backend'

/** The one signal vocabulary used everywhere in the redesigned stock
 * page (§12): strong / watch / risk / insufficient-data. Always paired
 * with text and an icon at the call site -- never color alone. */
export type SignalTone = 'strong' | 'watch' | 'risk' | 'insufficient'

export const TONE_LABEL: Record<SignalTone, string> = {
  strong: 'Strong',
  watch: 'Watch',
  risk: 'Risk',
  insufficient: 'Insufficient data',
}

export const TONE_ICON: Record<SignalTone, string> = {
  strong: '●',
  watch: '▲',
  risk: '■',
  insufficient: '○',
}

export const TONE_CLASS: Record<SignalTone, string> = {
  strong: 'tone-strong',
  watch: 'tone-watch',
  risk: 'tone-risk',
  insufficient: 'tone-insufficient',
}

export function toneFromBand(band: ScoreBand | null): SignalTone {
  if (band === null) return 'insufficient'
  if (band === 'excellent' || band === 'strong' || band === 'good') return 'strong'
  if (band === 'fair') return 'watch'
  return 'risk'
}

export function toneFromSeverity(severity: Severity | null): SignalTone {
  if (severity === null) return 'insufficient'
  if (severity === 'critical' || severity === 'high') return 'risk'
  if (severity === 'medium') return 'watch'
  return 'strong'
}
