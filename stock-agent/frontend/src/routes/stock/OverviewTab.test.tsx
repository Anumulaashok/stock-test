import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OverviewTab } from './OverviewTab'
import { renderWithStockReport } from '../../test/renderWithStockReport'

describe('OverviewTab', () => {
  it('renders the report once the provider is ready', async () => {
    await renderWithStockReport(<OverviewTab />, {
      company: { name: 'Acme Corp', ticker: 'ACME', currency: null },
    })

    expect(screen.getAllByText(/acme corp shows strong profitability/i).length).toBeGreaterThan(0)
  })
})
