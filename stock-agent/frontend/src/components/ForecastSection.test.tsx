import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ForecastSection } from './ForecastSection'
import { buildReport } from '../test/fixtures'
import type { ReportForecastSection } from '../types/backend'

function forecastFixture(overrides: Partial<ReportForecastSection> = {}): ReportForecastSection {
  return {
    source: 'forecast',
    available: true,
    projection_years: 2,
    financial_metrics: [
      {
        name: 'revenue', unit: 'USD', base_period: 'FY2025', base_value: '121',
        historical_cagr_percent: '10', status: 'calculated', reason: null,
        formatted_historical_cagr: '10.00%',
        projections: [
          { year_offset: 1, value: '133.1', status: 'calculated', formatted_value: '$133.10' },
          { year_offset: 2, value: '146.41', status: 'calculated', formatted_value: '$146.41' },
        ],
      },
    ],
    valuation_scenarios: [
      { scenario: 'bear', fcf_growth_rate: '0.05', value_per_share: '90', status: 'calculated', reason: null, formatted_value_per_share: '$90.00' },
      { scenario: 'base', fcf_growth_rate: '0.07', value_per_share: '110', status: 'calculated', reason: null, formatted_value_per_share: '$110.00' },
      { scenario: 'bull', fcf_growth_rate: '0.09', value_per_share: '135', status: 'calculated', reason: null, formatted_value_per_share: '$135.00' },
    ],
    price_trend: [{ day_offset: 1, projected_price: '101', formatted_projected_price: '$101.00' }],
    price_trend_status: 'calculated',
    price_trend_reason: null,
    price_trend_disclaimer: 'Naive statistical extrapolation... not a prediction of future performance.',
    ...overrides,
  }
}

describe('ForecastSection', () => {
  it('renders financial projections, valuation scenarios, and the price trend disclaimer', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    expect(screen.getByText('$146.41')).toBeInTheDocument()
    expect(screen.getByText('Bear')).toBeInTheDocument()
    expect(screen.getByText('$135.00')).toBeInTheDocument()
    expect(screen.getByText(/not a prediction of future performance/i)).toBeInTheDocument()
  })

  it('never labels the forecast a recommendation or a target price', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    expect(screen.getByText(/not a recommendation/i)).toBeInTheDocument()
    expect(screen.queryByText(/^target price$/i)).not.toBeInTheDocument()
  })

  it('renders nothing when the forecast is unavailable', () => {
    const { container } = render(<ForecastSection forecast={buildReport().forecast} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when forecast is null', () => {
    const { container } = render(<ForecastSection forecast={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
