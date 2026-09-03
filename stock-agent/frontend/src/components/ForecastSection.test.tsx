import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ForecastSection, sampleHistoricalPrices, buildMethodMarkers } from './ForecastSection'
import { buildReport } from '../test/fixtures'
import type {
  ReportForecastSection,
  ReportHistoricalPricePoint,
  ReportHorizonForecast,
  ReportTechnicalMethod,
} from '../types/backend'

function horizonFixture(overrides: Partial<ReportHorizonForecast> = {}): ReportHorizonForecast {
  return {
    horizon: 'daily',
    label: '30 Trading Days',
    price_trend: [{ period: 1, day_offset: 1, date: '2026-08-28', projected_price: '101', formatted_projected_price: '$101.00' }],
    price_trend_status: 'calculated',
    price_trend_reason: null,
    moving_averages: [
      { window: 50, value: '105', status: 'calculated', reason: null, formatted_value: '$105.00' },
      { window: 200, value: '95', status: 'calculated', reason: null, formatted_value: '$95.00' },
    ],
    crossover: { short_window: 50, long_window: 200, signal: 'golden_cross', status: 'calculated', reason: null },
    technical_methods: [
      {
        method: 'sma_50', description: '50-day SMA', projected_price: '105', projection_days: 5,
        horizon: 'daily', horizon_period: 30,
        projected_date: '2026-09-01',
        status: 'calculated', reason: null, formatted_projected_price: '$105.00',
      },
    ],
    technical_signal: { label: 'bullish', color: 'green', reason: 'Golden cross with price confirming.' },
    ...overrides,
  }
}

const HISTORICAL_PRICES: ReportHistoricalPricePoint[] = [
  { date: '2026-08-25', close: '98', formatted_close: '$98.00' },
  { date: '2026-08-26', close: '99', formatted_close: '$99.00' },
  { date: '2026-08-27', close: '100', formatted_close: '$100.00' },
]

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
    price_trend: [{ period: 1, day_offset: 1, date: '2026-08-28', projected_price: '101', formatted_projected_price: '$101.00' }],
    price_trend_status: 'calculated',
    price_trend_reason: null,
    price_trend_disclaimer: 'Naive statistical extrapolation... not a prediction of future performance.',
    moving_averages: [
      { window: 50, value: '105', status: 'calculated', reason: null, formatted_value: '$105.00' },
      { window: 200, value: '95', status: 'calculated', reason: null, formatted_value: '$95.00' },
    ],
    crossover: { short_window: 50, long_window: 200, signal: 'golden_cross', status: 'calculated', reason: null },
    technical_methods: [
      {
        method: 'sma_50', description: '50-day SMA', projected_price: '105', projection_days: 5,
        horizon: 'daily', horizon_period: 30,
        projected_date: '2026-09-01',
        status: 'calculated', reason: null, formatted_projected_price: '$105.00',
      },
    ],
    technical_disclaimer: 'Technical indicators are heuristics, not predictions.',
    technical_signal: { label: 'bullish', color: 'green', reason: 'Golden cross with price confirming.' },
    current_price: '100',
    formatted_current_price: '$100.00',
    horizons: {
      daily: horizonFixture({
        horizon: 'daily',
        label: '30 Trading Days',
        price_trend: [{ period: 1, day_offset: 1, date: '2026-08-28', projected_price: '101', formatted_projected_price: '$101.00' }],
      }),
      weekly: horizonFixture({
        horizon: 'weekly',
        label: '12 Weeks',
        price_trend: [
          { period: 1, day_offset: 5, date: '2026-09-01', projected_price: '108', formatted_projected_price: '$108.00' },
          { period: 12, day_offset: 60, date: '2026-11-16', projected_price: '150', formatted_projected_price: '$150.00' },
        ],
        technical_methods: [
          {
            method: 'sma_crossover_momentum', description: 'Momentum drift.', projected_price: '112', projection_days: 60,
            horizon: 'weekly', horizon_period: 12, projected_date: '2026-11-16',
            status: 'calculated', reason: null, formatted_projected_price: '$112.00',
          },
        ],
      }),
      monthly: horizonFixture({
        horizon: 'monthly',
        label: '12 Months',
        price_trend: [
          { period: 1, day_offset: 21, date: '2026-09-24', projected_price: '115', formatted_projected_price: '$115.00' },
          { period: 12, day_offset: 252, date: '2027-08-27', projected_price: '210', formatted_projected_price: '$210.00' },
        ],
        moving_averages: [
          { window: 50, value: '105', status: 'calculated', reason: null, formatted_value: '$105.00' },
          { window: 200, value: null, status: 'unavailable', reason: 'at least 200 historical closing prices are required (found 60)', formatted_value: null },
        ],
        technical_methods: [
          {
            method: 'sma_200', description: '200-day SMA reference.', projected_price: null, projection_days: 252,
            horizon: 'monthly', horizon_period: 12, projected_date: null,
            status: 'unavailable', reason: 'at least 200 historical closing prices are required (found 60)', formatted_projected_price: null,
          },
        ],
      }),
    },
    historical_prices: HISTORICAL_PRICES,
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

  it('renders the Daily/Weekly/Monthly horizon tabs with Daily selected by default', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual(['Daily', 'Weekly', 'Monthly'])
    expect(screen.getByRole('tab', { name: 'Daily' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('30 Trading Days')).toBeInTheDocument()
    expect(screen.getByText('2026-08-28: $101.00')).toBeInTheDocument()
  })

  it('switches to the weekly horizon and shows its own period points and label', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Weekly' }))

    expect(screen.getByRole('tab', { name: 'Weekly' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('12 Weeks')).toBeInTheDocument()
    expect(screen.getByText('2026-09-01: $108.00')).toBeInTheDocument()
    expect(screen.getByText('2026-11-16: $150.00')).toBeInTheDocument()
    // the daily horizon's point must no longer be shown
    expect(screen.queryByText('2026-08-28: $101.00')).not.toBeInTheDocument()
  })

  it('switches to the monthly horizon and keeps DCF scenarios shown separately from the trend chart', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Monthly' }))

    expect(screen.getByText('12 Months')).toBeInTheDocument()
    expect(screen.getByText('2027-08-27: $210.00')).toBeInTheDocument()
    // DCF scenarios are rendered once, outside the horizon panel, and
    // stay visible regardless of which horizon tab is active.
    expect(screen.getByText('Valuation Scenarios (DCF)')).toBeInTheDocument()
    expect(screen.getByText('$135.00')).toBeInTheDocument()
  })

  it('shows an unavailable method with its reason instead of hiding it', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Monthly' }))

    expect(screen.getByText('Sma 200')).toBeInTheDocument()
    expect(screen.getByText(/at least 200 historical closing prices are required/i)).toBeInTheDocument()
  })

  it('renders a Historical legend entry distinct from the Forecast trend when history is available', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    expect(screen.getByText('Historical')).toBeInTheDocument()
    expect(screen.getByText('Forecast trend')).toBeInTheDocument()
  })

  it('omits the Historical legend entry when no historical prices are available', () => {
    render(<ForecastSection forecast={forecastFixture({ historical_prices: [] })} />)
    expect(screen.queryByText('Historical')).not.toBeInTheDocument()
    expect(screen.getByText('Forecast trend')).toBeInTheDocument()
  })

  it('renders nothing horizon-specific when the report has no horizons (legacy contract)', () => {
    render(<ForecastSection forecast={forecastFixture({ horizons: null })} />)
    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
    // financial projections and DCF scenarios are horizon-independent and still render
    expect(screen.getByText('Valuation Scenarios (DCF)')).toBeInTheDocument()
  })
})

describe('sampleHistoricalPrices', () => {
  it('returns an empty array when there is no usable close', () => {
    expect(sampleHistoricalPrices([], 'daily')).toEqual([])
    expect(sampleHistoricalPrices([{ date: '2026-01-01', close: null, formatted_close: null }], 'daily')).toEqual([])
  })

  it('daily takes every trailing close, ending at day -1', () => {
    const prices: ReportHistoricalPricePoint[] = [
      { date: '2026-01-01', close: '10', formatted_close: null },
      { date: '2026-01-02', close: '11', formatted_close: null },
      { date: '2026-01-03', close: '12', formatted_close: null },
    ]
    expect(sampleHistoricalPrices(prices, 'daily')).toEqual([
      { day: -3, value: 10 },
      { day: -2, value: 11 },
      { day: -1, value: 12 },
    ])
  })

  it('weekly samples every 5th close counting backward, most recent always included', () => {
    const prices: ReportHistoricalPricePoint[] = Array.from({ length: 11 }, (_, i) => ({
      date: `2026-01-${String(i + 1).padStart(2, '0')}`,
      close: String(i),
      formatted_close: null,
    }))
    // indices 10, 5, 0 sampled backward -> chronological [0, 5, 10]
    expect(sampleHistoricalPrices(prices, 'weekly')).toEqual([
      { day: -3, value: 0 },
      { day: -2, value: 5 },
      { day: -1, value: 10 },
    ])
  })

  it('caps the point count at the horizon maximum (12 for monthly)', () => {
    const prices: ReportHistoricalPricePoint[] = Array.from({ length: 300 }, (_, i) => ({
      date: `day-${i}`,
      close: String(i),
      formatted_close: null,
    }))
    const sampled = sampleHistoricalPrices(prices, 'monthly')
    expect(sampled).toHaveLength(12)
    expect(sampled[sampled.length - 1].value).toBe(299)
    expect(sampled[sampled.length - 1].day).toBe(-1)
  })
})

describe('buildMethodMarkers', () => {
  it('positions each marker at the method horizon_period, not projection_days', () => {
    const methods: ReportTechnicalMethod[] = [
      {
        method: 'rate_of_change_momentum', description: '', projected_price: '120', projection_days: 60,
        horizon: 'weekly', horizon_period: 12, projected_date: '2026-11-16',
        status: 'calculated', reason: null, formatted_projected_price: '$120.00',
      },
    ]
    const markers = buildMethodMarkers(methods)
    expect(markers).toHaveLength(1)
    expect(markers[0].day).toBe(12)
  })

  it('excludes linear_regression (already the trend line) and non-calculated methods', () => {
    const methods: ReportTechnicalMethod[] = [
      {
        method: 'linear_regression', description: '', projected_price: '120', projection_days: 30,
        horizon: 'daily', horizon_period: 30, projected_date: '2026-09-27',
        status: 'calculated', reason: null, formatted_projected_price: '$120.00',
      },
      {
        method: 'sma_crossover_momentum', description: '', projected_price: null, projection_days: 30,
        horizon: 'daily', horizon_period: 30, projected_date: null,
        status: 'unavailable', reason: 'unavailable', formatted_projected_price: null,
      },
    ]
    expect(buildMethodMarkers(methods)).toEqual([])
  })
})
