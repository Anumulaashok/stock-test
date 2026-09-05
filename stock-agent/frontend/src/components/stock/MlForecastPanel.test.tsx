import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MlForecastPanel, resolvedPredictionMarkers } from './MlForecastPanel'
import * as mlForecastApi from '../../api/mlForecast'
import type { MlForecastHistoryResponse, MlForecastPrediction, MlForecastResult, MlHorizonForecast } from '../../types/mlForecast'
import type { ReportHistoricalPricePoint } from '../../types/backend'

function prediction(overrides: Partial<MlForecastPrediction> = {}): MlForecastPrediction {
  return {
    prediction_timestamp: '2026-08-01T09:00:00+00:00',
    horizon: '14D',
    predicted_return: 0.02,
    predicted_price: 102,
    target_date: '2026-08-15',
    actual_return: 0.03,
    actual_price: 103,
    direction_correct: true,
    forecast_quality: 'HIGH',
    model_version: 'v1',
    ...overrides,
  }
}

describe('resolvedPredictionMarkers', () => {
  it('includes only resolved predictions, excluding pending ones', () => {
    const resolved = prediction()
    const pending = prediction({ target_date: '2026-09-01', actual_return: null, actual_price: null })
    expect(resolvedPredictionMarkers([resolved, pending])).toEqual([
      { label: 'Past prediction', date: '2026-08-15', value: 102, color: '#c78a1f' },
    ])
  })

  it('returns an empty array when nothing has resolved yet', () => {
    expect(resolvedPredictionMarkers([prediction({ actual_return: null, actual_price: null })])).toEqual([])
  })
})

function horizonForecast(overrides: Partial<MlHorizonForecast> = {}): MlHorizonForecast {
  return {
    horizon: '14D',
    target_date: '2026-08-15',
    current_price: 100,
    expected_return: 0.02,
    expected_price: 102,
    quantiles: { p10: 98, p25: 100, p50: 102, p75: 104, p90: 106 },
    probability_positive: 0.6,
    forecast_quality: 'HIGH',
    quality_score: 0.8,
    quality_reasons: [],
    model_agreement: 0.7,
    model_outputs: [],
    drivers: { positive_drivers: [], negative_drivers: [] },
    analog: { sample_size: 0, is_reliable: false, positive_rate: null, negative_rate: null, mean_return: null, median_return: null, quantiles: null },
    historical_accuracy: null,
    ...overrides,
  }
}

function resultFixture(overrides: Partial<MlForecastResult> = {}): MlForecastResult {
  return {
    ticker: 'ACME',
    generated_at: '2026-08-14T00:00:00+00:00',
    data_date: '2026-08-14',
    current_price: 100,
    regime: 'TRENDING_UP',
    horizons: {
      '14D': horizonForecast(),
      '1M': horizonForecast({ horizon: '1M', target_date: '2026-09-14' }),
      '3M': horizonForecast({ horizon: '3M', target_date: '2026-11-14' }),
      '1Y': horizonForecast({ horizon: '1Y', target_date: '2027-08-14' }),
    },
    news_impact: { recent_events: [], historical_statistics: [], data_available: false, note: 'No news data.' },
    data_quality: { price_history_days: 400, fundamentals_available: true, news_available: false, regime: 'TRENDING_UP', training_data_end_date: '2026-08-14' },
    model_version: 'v1',
    feature_version: 'v1',
    news_model_version: 'v1',
    warnings: [],
    ...overrides,
  }
}

const HISTORICAL_PRICES: ReportHistoricalPricePoint[] = [
  { date: '2026-08-10', close: '99', formatted_close: '$99.00' },
  { date: '2026-08-14', close: '100', formatted_close: '$100.00' },
]

describe('MlForecastPanel resolved-prediction overlay', () => {
  it('fetches history for the selected horizon and shows the resolved-prediction caption when there is one', async () => {
    vi.spyOn(mlForecastApi, 'fetchMlForecast').mockResolvedValue(resultFixture())
    const fetchHistory = vi.spyOn(mlForecastApi, 'fetchMlForecastHistory').mockResolvedValue({
      ticker: 'ACME',
      predictions: [prediction()],
    } satisfies MlForecastHistoryResponse)

    render(<MlForecastPanel ticker="ACME" historicalPrices={HISTORICAL_PRICES} />)

    expect(await screen.findByText(/past predicted price for 14D forecasts/i)).toBeInTheDocument()
    expect(fetchHistory).toHaveBeenCalledWith('ACME', '14D', 200)
  })

  it('shows no caption when the selected horizon has no resolved predictions yet', async () => {
    vi.spyOn(mlForecastApi, 'fetchMlForecast').mockResolvedValue(resultFixture())
    vi.spyOn(mlForecastApi, 'fetchMlForecastHistory').mockResolvedValue({ ticker: 'ACME', predictions: [] })

    render(<MlForecastPanel ticker="ACME" historicalPrices={HISTORICAL_PRICES} />)

    await screen.findByRole('img', { name: /ai forecast price chart/i })
    expect(screen.queryByText(/past predicted price/i)).not.toBeInTheDocument()
  })

  it('refetches history for the newly selected horizon on tab switch', async () => {
    vi.spyOn(mlForecastApi, 'fetchMlForecast').mockResolvedValue(resultFixture())
    const fetchHistory = vi.spyOn(mlForecastApi, 'fetchMlForecastHistory').mockImplementation(async (_ticker, horizon) => ({
      ticker: 'ACME',
      predictions: horizon === '1M' ? [prediction({ horizon: '1M', target_date: '2026-09-01' })] : [],
    }))

    render(<MlForecastPanel ticker="ACME" historicalPrices={HISTORICAL_PRICES} />)
    await waitFor(() => expect(fetchHistory).toHaveBeenCalledWith('ACME', '14D', 200))

    await userEvent.click(screen.getByText('1M'))
    await waitFor(() => expect(fetchHistory).toHaveBeenCalledWith('ACME', '1M', 200))
    expect(await screen.findByText(/past predicted price for 1M forecasts/i)).toBeInTheDocument()
  })
})
