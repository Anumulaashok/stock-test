import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PriceChart, formatAxisDate } from './PriceChart'

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

describe('PriceChart', () => {
  it('renders a canvas inside a labeled image container without throwing', () => {
    render(
      <PriceChart
        historical={[
          { date: '2026-08-25', value: 98 },
          { date: '2026-08-26', value: 99 },
        ]}
        predicted={[
          { date: '2026-08-26', value: 99 },
          { date: '2026-08-27', value: 101 },
        ]}
        ariaLabel="Forecast price chart"
      />,
    )
    const container = screen.getByRole('img', { name: /forecast price chart/i })
    expect(container.querySelector('canvas')).toBeInTheDocument()
  })

  it('defaults to a generic "Price chart" label when the caller does not name one', () => {
    render(<PriceChart historical={[{ date: '2026-08-25', value: 98 }]} predicted={[]} />)
    expect(screen.getByRole('img', { name: 'Price chart' })).toBeInTheDocument()
  })

  it('renders with markers and reference lines and does not throw', () => {
    render(
      <PriceChart
        historical={[{ date: '2026-08-25', value: 98 }]}
        predicted={[]}
        markers={[{ label: 'SMA crossover', date: '2026-08-26', value: 100, color: '#b5540a' }]}
        referenceLines={[{ label: '50-day SMA', value: 97, color: '#8a6d00' }]}
        ariaLabel="Forecast price chart"
      />,
    )
    expect(screen.getByRole('img', { name: /forecast price chart/i })).toBeInTheDocument()
  })

  it('re-renders cleanly when data changes (destroys and recreates the chart instance)', () => {
    const { rerender } = render(
      <PriceChart historical={[{ date: '2026-08-25', value: 98 }]} predicted={[]} ariaLabel="Forecast price chart" />,
    )
    rerender(<PriceChart historical={[{ date: '2026-08-26', value: 99 }]} predicted={[]} ariaLabel="Forecast price chart" />)
    expect(screen.getByRole('img', { name: /forecast price chart/i })).toBeInTheDocument()
  })

  it('renders edge markers without throwing (right-edge stub, not a full-width line)', () => {
    render(
      <PriceChart
        historical={[
          { date: '2026-08-25', value: 98 },
          { date: '2026-08-26', value: 99 },
        ]}
        predicted={[]}
        edgeMarkers={[{ label: '50-day SMA', value: 95, color: '#8a6d00' }]}
        ariaLabel="Price chart"
      />,
    )
    expect(screen.getByRole('img', { name: 'Price chart' })).toBeInTheDocument()
  })

  it('renders no volume sub-chart when volume is omitted', () => {
    render(<PriceChart historical={[{ date: '2026-08-25', value: 98 }]} predicted={[]} ariaLabel="Price chart" />)
    expect(screen.queryByRole('img', { name: /price chart volume/i })).not.toBeInTheDocument()
  })

  it('renders a volume sub-chart in its own labeled container when volume is provided', () => {
    render(
      <PriceChart
        historical={[
          { date: '2026-08-25', value: 98 },
          { date: '2026-08-26', value: 99 },
        ]}
        predicted={[]}
        volume={[
          { date: '2026-08-25', value: 1200 },
          { date: '2026-08-26', value: 1500 },
        ]}
        ariaLabel="Price chart"
      />,
    )
    const volumeContainer = screen.getByRole('img', { name: /price chart volume/i })
    expect(volumeContainer.querySelector('canvas')).toBeInTheDocument()
  })

  it('re-renders cleanly when volume changes (destroys and recreates the volume chart instance)', () => {
    const { rerender } = render(
      <PriceChart
        historical={[{ date: '2026-08-25', value: 98 }]}
        predicted={[]}
        volume={[{ date: '2026-08-25', value: 1200 }]}
        ariaLabel="Price chart"
      />,
    )
    rerender(
      <PriceChart
        historical={[{ date: '2026-08-25', value: 98 }]}
        predicted={[]}
        volume={[{ date: '2026-08-25', value: 1400 }]}
        ariaLabel="Price chart"
      />,
    )
    expect(screen.getByRole('img', { name: /price chart volume/i })).toBeInTheDocument()
  })
})
