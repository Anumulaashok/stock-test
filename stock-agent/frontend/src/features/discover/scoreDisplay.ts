import { toDisplayNumber } from '../../lib/format'

/** A null score/band means the backend could not calculate it -- always
 * say so explicitly rather than falling back to 0 or a blank cell. */
export const UNAVAILABLE = 'Unavailable'

export function scoreText(value: string | null): string {
  const formatted = toDisplayNumber(value, 0)
  return formatted ?? UNAVAILABLE
}
