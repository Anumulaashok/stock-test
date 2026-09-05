import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SkeletonHoldingsTable, SkeletonWatchlistRows } from './Skeleton'

describe('SkeletonWatchlistRows', () => {
  it('renders one loading region with the requested row count', () => {
    render(<SkeletonWatchlistRows count={2} />)
    const region = screen.getByRole('status', { name: /loading watchlist/i })
    expect(region.children).toHaveLength(2)
  })
})

describe('SkeletonHoldingsTable', () => {
  it('mirrors the real table header columns', () => {
    render(<SkeletonHoldingsTable count={2} />)
    for (const label of ['Ticker', 'Quantity', 'Avg Cost', 'Price', 'Value', 'Gain / Loss']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('renders the requested row count as a loading region', () => {
    render(<SkeletonHoldingsTable count={3} />)
    expect(screen.getByRole('status', { name: /loading holdings/i })).toBeInTheDocument()
  })
})
