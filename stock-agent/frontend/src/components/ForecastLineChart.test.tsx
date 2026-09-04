import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ForecastLineChart, formatAxisDate } from './ForecastLineChart'

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

describe('ForecastLineChart', () => {
  it('renders a canvas inside a labeled image container without throwing', () => {
    render(
      <ForecastLineChart
        historical={[
          { date: '2026-08-25', value: 98 },
          { date: '2026-08-26', value: 99 },
        ]}
        predicted={[
          { date: '2026-08-26', value: 99 },
          { date: '2026-08-27', value: 101 },
        ]}
      />,
    )
    const container = screen.getByRole('img', { name: /forecast price chart/i })
    expect(container.querySelector('canvas')).toBeInTheDocument()
  })

  it('renders with markers and reference lines and does not throw', () => {
    render(
      <ForecastLineChart
        historical={[{ date: '2026-08-25', value: 98 }]}
        predicted={[]}
        markers={[{ label: 'SMA crossover', date: '2026-08-26', value: 100, color: '#b5540a' }]}
        referenceLines={[{ label: '50-day SMA', value: 97, color: '#8a6d00' }]}
      />,
    )
    expect(screen.getByRole('img', { name: /forecast price chart/i })).toBeInTheDocument()
  })

  it('re-renders cleanly when data changes (destroys and recreates the chart instance)', () => {
    const { rerender } = render(<ForecastLineChart historical={[{ date: '2026-08-25', value: 98 }]} predicted={[]} />)
    rerender(<ForecastLineChart historical={[{ date: '2026-08-26', value: 99 }]} predicted={[]} />)
    expect(screen.getByRole('img', { name: /forecast price chart/i })).toBeInTheDocument()
  })
})
