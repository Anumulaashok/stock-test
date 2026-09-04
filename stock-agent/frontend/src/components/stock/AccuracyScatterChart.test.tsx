import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AccuracyScatterChart, MIN_N_FOR_QUADRANT_SHADING, partitionByDirection } from './AccuracyScatterChart'
import type { AccuracyScatterPoint } from './AccuracyScatterChart'

describe('partitionByDirection', () => {
  it('is authoritative from directionCorrect alone, never recomputed from the point coordinates', () => {
    // predicted_return === 0 is the boundary the backend's own
    // `(actual_return > 0) == (predicted_return > 0)` rule treats as
    // "not positive" -- direction_correct is False here even though the
    // point sits exactly on the quadrant boundary line (x=0), not
    // visually inside either "incorrect" quadrant.
    const boundaryPoint: AccuracyScatterPoint = {
      targetDate: '2026-08-15',
      predictedReturn: 0,
      actualReturn: 0.01,
      directionCorrect: false,
    }
    const { correct, incorrect, unclassified } = partitionByDirection([boundaryPoint])
    expect(incorrect).toEqual([boundaryPoint])
    expect(correct).toEqual([])
    expect(unclassified).toEqual([])
  })

  it('buckets a null direction_correct as unclassified, never as correct or incorrect', () => {
    const point: AccuracyScatterPoint = {
      targetDate: '2026-08-15',
      predictedReturn: 0.01,
      actualReturn: -0.01,
      directionCorrect: null,
    }
    const { correct, incorrect, unclassified } = partitionByDirection([point])
    expect(unclassified).toEqual([point])
    expect(correct).toEqual([])
    expect(incorrect).toEqual([])
  })
})

function points(n: number): AccuracyScatterPoint[] {
  return Array.from({ length: n }, (_, i) => ({
    targetDate: `2026-08-${String(i + 1).padStart(2, '0')}`,
    predictedReturn: 0.01 * (i + 1),
    actualReturn: 0.01 * (i + 1),
    directionCorrect: true,
  }))
}

describe('AccuracyScatterChart', () => {
  it('renders below the quadrant-shading minimum without throwing', () => {
    render(<AccuracyScatterChart points={points(MIN_N_FOR_QUADRANT_SHADING - 1)} />)
    expect(screen.getByRole('img', { name: /predicted versus actual return scatter/i })).toBeInTheDocument()
  })

  it('renders at and above the quadrant-shading minimum without throwing', () => {
    render(<AccuracyScatterChart points={points(MIN_N_FOR_QUADRANT_SHADING)} />)
    expect(screen.getByRole('img', { name: /predicted versus actual return scatter/i })).toBeInTheDocument()
  })

  it('renders an empty scatter without throwing', () => {
    render(<AccuracyScatterChart points={[]} />)
    expect(screen.getByRole('img', { name: /predicted versus actual return scatter/i })).toBeInTheDocument()
  })
})
