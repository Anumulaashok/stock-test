import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MlAccuracyPanel } from './MlAccuracyPanel'
import * as mlForecastApi from '../../api/mlForecast'
import type { MlForecastAccuracyResponse, MlForecastHistoryResponse, MlForecastPrediction } from '../../types/mlForecast'

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

function emptyAccuracy(): MlForecastAccuracyResponse {
  return {
    ticker: 'ACME',
    accuracy_by_horizon: {
      '14D': { sample_size: 0, mae: null, rmse: null, directional_accuracy: null, brier_score: null, interval_coverage_80: null, note: 'No walk-forward evaluation recorded yet' },
    },
  }
}

describe('MlAccuracyPanel', () => {
  it('renders the fresh-DB empty state as "not evaluated yet," never as a 0% accuracy figure', async () => {
    vi.spyOn(mlForecastApi, 'fetchMlForecastAccuracy').mockResolvedValue(emptyAccuracy())
    vi.spyOn(mlForecastApi, 'fetchMlForecastHistory').mockResolvedValue({ ticker: 'ACME', predictions: [] })

    render(<MlAccuracyPanel ticker="ACME" />)

    expect(await screen.findByText(/not evaluated yet for 14D/i)).toBeInTheDocument()
    expect(await screen.findByText(/no walk-forward evaluation recorded yet/i)).toBeInTheDocument()
    expect(screen.getByText(/no predictions have been made for this horizon yet/i)).toBeInTheDocument()
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
  })

  it('excludes pending predictions from the resolved count and the scatter, and states the exclusion', async () => {
    const history: MlForecastHistoryResponse = {
      ticker: 'ACME',
      predictions: [
        prediction({ target_date: '2026-08-15', actual_return: 0.03, direction_correct: true }),
        prediction({ target_date: '2026-09-01', actual_return: null, actual_price: null, direction_correct: null }),
      ],
    }
    vi.spyOn(mlForecastApi, 'fetchMlForecastAccuracy').mockResolvedValue(emptyAccuracy())
    vi.spyOn(mlForecastApi, 'fetchMlForecastHistory').mockResolvedValue(history)

    render(<MlAccuracyPanel ticker="ACME" />)

    expect(await screen.findByText(/1 resolved · 1 pending/i)).toBeInTheDocument()
    expect(screen.getByText(/excluded from every accuracy figure below/i)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /predicted versus actual return scatter/i })).toBeInTheDocument()
  })

  it('renders populated walk-forward stats with sample size shown next to every figure', async () => {
    const accuracy: MlForecastAccuracyResponse = {
      ticker: 'ACME',
      accuracy_by_horizon: {
        '14D': {
          sample_size: 23,
          mae: 0.015,
          rmse: 0.021,
          directional_accuracy: 0.65,
          brier_score: 0.18,
          interval_coverage_80: 0.78,
        },
      },
    }
    vi.spyOn(mlForecastApi, 'fetchMlForecastAccuracy').mockResolvedValue(accuracy)
    vi.spyOn(mlForecastApi, 'fetchMlForecastHistory').mockResolvedValue({
      ticker: 'ACME',
      predictions: [prediction()],
    })

    render(<MlAccuracyPanel ticker="ACME" />)

    expect(await screen.findByText('65.0%')).toBeInTheDocument()
    expect(screen.getAllByText('n=23').length).toBeGreaterThan(0)
  })

  it('fetches history per-horizon (never one unfiltered call bucketed client-side), switching data on tab click', async () => {
    const fetchHistory = vi.spyOn(mlForecastApi, 'fetchMlForecastHistory').mockImplementation(async (_ticker, horizon) => {
      if (horizon === '1M') {
        return { ticker: 'ACME', predictions: [prediction({ horizon: '1M', actual_return: null, actual_price: null, direction_correct: null })] }
      }
      return { ticker: 'ACME', predictions: [] }
    })
    vi.spyOn(mlForecastApi, 'fetchMlForecastAccuracy').mockResolvedValue(emptyAccuracy())

    render(<MlAccuracyPanel ticker="ACME" />)
    await waitFor(() => expect(screen.getByText(/0 resolved · 0 pending/i)).toBeInTheDocument())
    expect(fetchHistory).toHaveBeenCalledWith('ACME', '14D', 200)

    await userEvent.click(screen.getByRole('button', { name: '1M' }))
    await waitFor(() => expect(screen.getByText(/0 resolved · 1 pending/i)).toBeInTheDocument())
    expect(fetchHistory).toHaveBeenCalledWith('ACME', '1M', 200)
  })

  it('suppresses quadrant shading below the calibration minimum but still plots the real points', async () => {
    const predictions = Array.from({ length: 3 }, (_, i) =>
      prediction({ target_date: `2026-08-0${i + 1}`, actual_return: 0.01 * (i + 1), direction_correct: true }),
    )
    vi.spyOn(mlForecastApi, 'fetchMlForecastAccuracy').mockResolvedValue(emptyAccuracy())
    vi.spyOn(mlForecastApi, 'fetchMlForecastHistory').mockResolvedValue({ ticker: 'ACME', predictions })

    render(<MlAccuracyPanel ticker="ACME" />)

    expect(await screen.findByText(/too few for a calibration read/i)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /predicted versus actual return scatter/i })).toBeInTheDocument()
  })
})
