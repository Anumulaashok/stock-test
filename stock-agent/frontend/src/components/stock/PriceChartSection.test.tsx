import { render as rtlRender, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import { describe, expect, it } from 'vitest'
import { PriceChartSection, historicalVolume, currentSmaEdgeMarkers } from './PriceChartSection'
import type { ReportForecastSection, ReportHistoricalPricePoint } from '../../types/backend'
import { ThemeProvider } from '../../theme/ThemeContext'

function render(ui: ReactElement) {
  return rtlRender(ui, { wrapper: ThemeProvider })
}

const HISTORICAL_PRICES: ReportHistoricalPricePoint[] = [
  { date: '2026-08-25', close: '98', volume: '1200', formatted_close: '$98.00' },
  { date: '2026-08-26', close: '99', volume: '1500', formatted_close: '$99.00' },
]

function forecastFixture(overrides: Partial<ReportForecastSection> = {}): ReportForecastSection {
  return {
    source: 'forecast',
    available: true,
    projection_years: 2,
    financial_metrics: [],
    valuation_scenarios: [],
    price_trend: [],
    price_trend_status: null,
    price_trend_reason: null,
    price_trend_disclaimer: null,
    moving_averages: [
      { window: 50, value: '95', status: 'calculated', reason: null, formatted_value: '$95.00' },
      { window: 200, value: '90', status: 'calculated', reason: null, formatted_value: '$90.00' },
    ],
    crossover: { short_window: 50, long_window: 200, signal: 'golden_cross', status: 'calculated', reason: null },
    technical_methods: [],
    technical_disclaimer: null,
    technical_signal: null,
    current_price: '99',
    formatted_current_price: '$99.00',
    horizons: null,
    historical_prices: HISTORICAL_PRICES,
    ...overrides,
  }
}

describe('historicalVolume', () => {
  it('reshapes volume chronologically, dropping points with no numeric volume', () => {
    expect(
      historicalVolume(
        forecastFixture({
          historical_prices: [
            { date: '2026-08-26', close: '99', volume: '1500', formatted_close: '$99.00' },
            { date: '2026-08-25', close: '98', volume: null, formatted_close: '$98.00' },
          ],
        }),
      ),
    ).toEqual([{ date: '2026-08-26', value: 1500 }])
  })
})

describe('currentSmaEdgeMarkers', () => {
  it('returns right-edge markers for the current SMA level, never a full-width reference line', () => {
    const markers = currentSmaEdgeMarkers(forecastFixture())
    expect(markers).toEqual([
      { label: '50-day SMA', value: 95, color: '#8a6d00' },
      { label: '200-day SMA', value: 90, color: '#7a3ab3' },
    ])
  })
})

describe('PriceChartSection', () => {
  it('renders the chart, the crossover badge, and the SMA-is-current-value caveat', () => {
    render(<PriceChartSection forecast={forecastFixture()} />)
    expect(screen.getByRole('img', { name: 'Price chart' })).toBeInTheDocument()
    expect(screen.getByText('Golden Cross')).toBeInTheDocument()
    expect(screen.getByText(/not a moving trace across history/i)).toBeInTheDocument()
  })

  it('renders a volume sub-chart when historical_prices carries volume', () => {
    render(<PriceChartSection forecast={forecastFixture()} />)
    expect(screen.getByRole('img', { name: /price chart volume/i })).toBeInTheDocument()
  })

  it('shows the honest empty state with an import-history link when there is no price history', () => {
    render(<PriceChartSection forecast={forecastFixture({ historical_prices: [] })} />)
    expect(screen.getByText(/no price history to chart/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /settings.*import historical data/i })).toHaveAttribute(
      'href',
      '/settings/system',
    )
    expect(screen.queryByRole('img', { name: 'Price chart' })).not.toBeInTheDocument()
  })

  it('renders nothing when forecast is unavailable', () => {
    const { container } = render(<PriceChartSection forecast={forecastFixture({ available: false })} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when forecast is null', () => {
    const { container } = render(<PriceChartSection forecast={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
