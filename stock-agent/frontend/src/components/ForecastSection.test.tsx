import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ForecastSection, allHistoricalPrices, buildMethodCards, buildMethodMarkers, predictedPrices } from './ForecastSection'
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
    financial_metrics: [],
    valuation_scenarios: [],
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
  it('shows the current price and the disclaimer, and nothing else text-heavy', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    expect(screen.getByText('$100.00')).toBeInTheDocument()
    expect(screen.getByText(/not a prediction of future performance/i)).toBeInTheDocument()
  })

  it('never labels the forecast a recommendation or a target price', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    expect(screen.queryByText(/^target price$/i)).not.toBeInTheDocument()
  })

  it('does not render financial projections or DCF valuation scenarios -- chart only', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    expect(screen.queryByText('Financial Projections')).not.toBeInTheDocument()
    expect(screen.queryByText('Valuation Scenarios (DCF)')).not.toBeInTheDocument()
    expect(screen.queryByText('Bear')).not.toBeInTheDocument()
  })

  it('does not render a numeric "Expected"/"Predicted" summary panel or a technical-signals grid', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    expect(screen.queryByText('Forecast Summary')).not.toBeInTheDocument()
    expect(screen.queryByText('Technical Signals')).not.toBeInTheDocument()
  })

  it('renders the chart as an svg image', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    expect(screen.getByRole('img', { name: /forecast price chart/i })).toBeInTheDocument()
  })

  it('always shows a "Not backtested" badge, regardless of horizon', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    expect(screen.getByText('Not backtested')).toBeInTheDocument()
  })

  it('shows a method card (including linear_regression) alongside the chart, parallel and never averaged', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    expect(screen.getByText('50-day SMA')).toBeInTheDocument()
    expect(screen.getByText('$105.00')).toBeInTheDocument()
  })

  it('renders nothing when the forecast is unavailable', () => {
    const { container } = render(<ForecastSection forecast={forecastFixture({ available: false })} />)
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
  })

  it('switches to the weekly horizon and shows its own label', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Weekly' }))
    expect(screen.getByText('12 Weeks')).toBeInTheDocument()
  })

  it('renders a Historical legend entry distinct from Predicted when history is available', () => {
    render(<ForecastSection forecast={forecastFixture()} />)
    expect(screen.getByText('Historical')).toBeInTheDocument()
    expect(screen.getByText('Predicted')).toBeInTheDocument()
  })

  it('omits the Historical legend entry when no historical prices are available', () => {
    render(<ForecastSection forecast={forecastFixture({ historical_prices: [] })} />)
    expect(screen.queryByText('Historical')).not.toBeInTheDocument()
    expect(screen.getByText('Predicted')).toBeInTheDocument()
  })

  it('renders nothing when the report has no horizons (legacy contract)', () => {
    const { container } = render(<ForecastSection forecast={forecastFixture({ horizons: null })} />)
    expect(container).toBeEmptyDOMElement()
  })

  describe('current price', () => {
    it('falls back to the market snapshot price when the forecast pipeline has none', () => {
      render(
        <ForecastSection
          forecast={forecastFixture({ current_price: null, formatted_current_price: null })}
          market={{
            source: 'yfinance', current_price: '250', previous_close: '245', change: '5', change_percent: '2.04',
            currency: 'INR', market_status: 'open', market_timestamp: null, freshness: 'delayed',
            market_cap: null, year_high: null, year_low: null, formatted_current_price: '₹250.00',
          }}
        />,
      )
      expect(screen.getByText('₹250.00')).toBeInTheDocument()
    })

    it('shows "Price unavailable" honestly when neither source has one', () => {
      render(<ForecastSection forecast={forecastFixture({ current_price: null, formatted_current_price: null })} market={null} />)
      expect(screen.getByText('Price unavailable')).toBeInTheDocument()
    })
  })

  describe('chart markers when the deterministic trend is unavailable', () => {
    function unavailableTrendFixture(technicalMethods: ReportTechnicalMethod[]) {
      return forecastFixture({
        horizons: {
          daily: horizonFixture({
            price_trend: [],
            price_trend_status: 'unavailable',
            price_trend_reason: 'at least 5 historical price points are required',
            technical_methods: technicalMethods,
          }),
          weekly: horizonFixture({ price_trend: [] }),
          monthly: horizonFixture({ price_trend: [] }),
        },
      })
    }

    it('still renders a chart (as marker points) when a technical method has a calculated value', () => {
      const forecast = unavailableTrendFixture([
        {
          method: 'sma_crossover_momentum', description: 'Momentum drift.', projected_price: '112',
          projection_days: 5, horizon: 'daily', horizon_period: 5, projected_date: '2026-09-05',
          status: 'calculated', reason: null, formatted_projected_price: '$112.00',
        },
      ])
      render(<ForecastSection forecast={forecast} />)
      expect(screen.getByRole('img', { name: /forecast price chart/i })).toBeInTheDocument()
    })

    it('shows an honest empty state, plus a historical-import hint, when nothing is chartable at all', () => {
      const forecast = {
        ...unavailableTrendFixture([
          {
            method: 'sma_50', description: '50-day SMA', projected_price: null, projection_days: 5,
            horizon: 'daily', horizon_period: 5, projected_date: null,
            status: 'unavailable', reason: 'at least 50 historical closing prices are required (found 0)',
            formatted_projected_price: null,
          },
        ]),
        historical_prices: [],
      }
      render(<ForecastSection forecast={forecast} />)

      expect(screen.queryByRole('img', { name: /forecast price chart/i })).not.toBeInTheDocument()
      expect(screen.getByText('at least 5 historical price points are required')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /settings.*system/i })).toHaveAttribute('href', '/settings/system')
    })

    it('shows historical prices with an honest "no prediction" note when only history is chartable', () => {
      const forecast = unavailableTrendFixture([
        {
          method: 'sma_50', description: '50-day SMA', projected_price: null, projection_days: 5,
          horizon: 'daily', horizon_period: 5, projected_date: null,
          status: 'unavailable', reason: 'at least 50 historical closing prices are required (found 0)',
          formatted_projected_price: null,
        },
      ])
      render(<ForecastSection forecast={forecast} />)

      expect(screen.getByRole('img', { name: /forecast price chart/i })).toBeInTheDocument()
      expect(screen.getByText(/no prediction available for this horizon/i)).toBeInTheDocument()
    })

    it('does not show the historical-import hint for a reason unrelated to missing price history', () => {
      const forecast = forecastFixture({
        horizons: {
          daily: horizonFixture({
            price_trend: [], price_trend_status: 'unavailable',
            price_trend_reason: 'current price is unavailable', technical_methods: [],
          }),
          weekly: horizonFixture({ price_trend: [] }),
          monthly: horizonFixture({ price_trend: [] }),
        },
      })
      render(<ForecastSection forecast={forecast} />)

      expect(screen.queryByRole('link', { name: /settings.*system/i })).not.toBeInTheDocument()
    })
  })
})

describe('allHistoricalPrices', () => {
  it('returns an empty array when there is no usable close', () => {
    expect(allHistoricalPrices([])).toEqual([])
    expect(allHistoricalPrices([{ date: '2026-08-25', close: null, formatted_close: null }])).toEqual([])
  })

  it('returns every usable close, chronologically -- never sampled or capped', () => {
    expect(allHistoricalPrices(HISTORICAL_PRICES)).toEqual([
      { date: '2026-08-25', value: 98 },
      { date: '2026-08-26', value: 99 },
      { date: '2026-08-27', value: 100 },
    ])
  })

  it('does not cap out at any fixed count, however much history exists', () => {
    const prices: ReportHistoricalPricePoint[] = Array.from({ length: 500 }, (_, i) => ({
      date: `2024-01-${String((i % 28) + 1).padStart(2, '0')}`,
      close: String(i),
      formatted_close: null,
    }))
    expect(allHistoricalPrices(prices).length).toBe(500)
  })
})

describe('predictedPrices', () => {
  it('returns nothing when there is no calculated trend', () => {
    const data = horizonFixture({ price_trend: [] })
    expect(predictedPrices(data, 100, '2026-08-27')).toEqual([])
  })

  it('bridges from the given anchor date/price into the trend', () => {
    const data = horizonFixture({
      price_trend: [{ period: 1, day_offset: 1, date: '2026-08-28', projected_price: '101', formatted_projected_price: '$101.00' }],
    })
    expect(predictedPrices(data, 100, '2026-08-27')).toEqual([
      { date: '2026-08-27', value: 100 },
      { date: '2026-08-28', value: 101 },
    ])
  })

  it('skips the bridge point when there is no current price or anchor date', () => {
    const data = horizonFixture({
      price_trend: [{ period: 1, day_offset: 1, date: '2026-08-28', projected_price: '101', formatted_projected_price: '$101.00' }],
    })
    expect(predictedPrices(data, null, '2026-08-27')).toEqual([{ date: '2026-08-28', value: 101 }])
    expect(predictedPrices(data, 100, null)).toEqual([{ date: '2026-08-28', value: 101 }])
  })
})

describe('buildMethodMarkers', () => {
  it('positions each marker at the method own projected_date', () => {
    const methods: ReportTechnicalMethod[] = [
      {
        method: 'sma_crossover_momentum', description: '', projected_price: '112', projection_days: 60,
        horizon: 'weekly', horizon_period: 12, projected_date: '2026-11-16', status: 'calculated', reason: null,
        formatted_projected_price: '$112.00',
      },
    ]
    const markers = buildMethodMarkers(methods)
    expect(markers).toEqual([{ label: 'Sma Crossover Momentum', date: '2026-11-16', value: 112, color: '#b5540a' }])
  })

  it('excludes linear_regression (already the trend line), non-calculated methods, and a missing date', () => {
    const methods: ReportTechnicalMethod[] = [
      {
        method: 'linear_regression', description: '', projected_price: '100', projection_days: 5,
        horizon: 'daily', horizon_period: 5, projected_date: '2026-09-05', status: 'calculated', reason: null,
        formatted_projected_price: '$100.00',
      },
      {
        method: 'sma_50', description: '', projected_price: null, projection_days: 5,
        horizon: 'daily', horizon_period: 5, projected_date: null, status: 'unavailable', reason: 'n/a',
        formatted_projected_price: null,
      },
      {
        method: 'rate_of_change_momentum', description: '', projected_price: '110', projection_days: 5,
        horizon: 'daily', horizon_period: 5, projected_date: null, status: 'calculated', reason: null,
        formatted_projected_price: '$110.00',
      },
    ]
    expect(buildMethodMarkers(methods)).toEqual([])
  })
})

describe('buildMethodCards', () => {
  it('includes linear_regression (unlike buildMethodMarkers) with a humanized label, one card per method', () => {
    const methods: ReportTechnicalMethod[] = [
      { method: 'linear_regression', description: 'OLS trend.', projected_price: '100', projection_days: 5, horizon: 'daily', horizon_period: 5, projected_date: '2026-09-05', status: 'calculated', reason: null, formatted_projected_price: '$100.00' },
      { method: 'sma_50', description: '50-day SMA.', projected_price: '95', projection_days: 5, horizon: 'daily', horizon_period: 5, projected_date: '2026-09-05', status: 'calculated', reason: null, formatted_projected_price: '$95.00' },
      { method: 'sma_200', description: '200-day SMA.', projected_price: '90', projection_days: 5, horizon: 'daily', horizon_period: 5, projected_date: '2026-09-05', status: 'calculated', reason: null, formatted_projected_price: '$90.00' },
      { method: 'sma_crossover_momentum', description: 'Momentum drift.', projected_price: '102', projection_days: 5, horizon: 'daily', horizon_period: 5, projected_date: '2026-09-05', status: 'calculated', reason: null, formatted_projected_price: '$102.00' },
    ]
    expect(buildMethodCards(methods)).toEqual([
      { method: 'linear_regression', label: 'Linear Regression', description: 'OLS trend.', targetDate: '2026-09-05', formattedProjectedPrice: '$100.00', status: 'calculated', reason: null },
      { method: 'sma_50', label: '50-day SMA', description: '50-day SMA.', targetDate: '2026-09-05', formattedProjectedPrice: '$95.00', status: 'calculated', reason: null },
      { method: 'sma_200', label: '200-day SMA', description: '200-day SMA.', targetDate: '2026-09-05', formattedProjectedPrice: '$90.00', status: 'calculated', reason: null },
      { method: 'sma_crossover_momentum', label: 'Crossover Momentum', description: 'Momentum drift.', targetDate: '2026-09-05', formattedProjectedPrice: '$102.00', status: 'calculated', reason: null },
    ])
  })

  it('falls back to a humanized method name for an unrecognized method', () => {
    const methods: ReportTechnicalMethod[] = [
      { method: 'rate_of_change_momentum', description: '', projected_price: '100', projection_days: 5, horizon: 'daily', horizon_period: 5, projected_date: '2026-09-05', status: 'calculated', reason: null, formatted_projected_price: '$100.00' },
    ]
    expect(buildMethodCards(methods)[0].label).toBe('Rate Of Change Momentum')
  })

  it('carries the unavailable status and reason through, rather than a fabricated value', () => {
    const methods: ReportTechnicalMethod[] = [
      { method: 'sma_50', description: '', projected_price: null, projection_days: 5, horizon: 'daily', horizon_period: 5, projected_date: null, status: 'unavailable', reason: 'insufficient history', formatted_projected_price: null },
    ]
    expect(buildMethodCards(methods)).toEqual([
      { method: 'sma_50', label: '50-day SMA', description: '', targetDate: null, formattedProjectedPrice: null, status: 'unavailable', reason: 'insufficient history' },
    ])
  })
})
