/** Shared positive/negative color decision for a nullable decimal-string
 * gain figure -- a missing value renders neutral, never green or red. */
export function toneFor(value: string | null | undefined): 'positive' | 'negative' | undefined {
  if (value === null || value === undefined) return undefined
  const parsed = Number(value)
  if (Number.isNaN(parsed)) return undefined
  return parsed >= 0 ? 'positive' : 'negative'
}

export function toneClass(tone: 'positive' | 'negative' | undefined): string {
  if (tone === 'positive') return 'text-[var(--color-status-positive)]'
  if (tone === 'negative') return 'text-[var(--color-status-negative)]'
  return 'text-[var(--color-text)]'
}
