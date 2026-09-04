import { describe, expect, it } from 'vitest'
import { formatAxisDate } from './ForecastLineChart'

describe('formatAxisDate', () => {
  it('formats a plain date', () => {
    expect(formatAxisDate('2026-07-24')).toBe('Jul 24')
  })

  it('formats a full ISO datetime with an offset, without ever falling back to the raw string', () => {
    const result = formatAxisDate('2026-07-24T00:00:00+05:30')
    expect(result).toBe('Jul 24')
    expect(result).not.toContain('T00:00:00')
  })

  it('does not shift a plain date to the previous day in a timezone behind UTC', () => {
    // A bare "YYYY-MM-DD" parsed as UTC midnight (`new Date(iso)`) would
    // render as the previous day in any timezone west of UTC -- this is
    // the exact regression the local-time constructor path guards
    // against.
    expect(formatAxisDate('2026-01-01')).toBe('Jan 1')
  })

  it('falls back to the raw string for something genuinely unparseable', () => {
    expect(formatAxisDate('not-a-date')).toBe('not-a-date')
  })
})
