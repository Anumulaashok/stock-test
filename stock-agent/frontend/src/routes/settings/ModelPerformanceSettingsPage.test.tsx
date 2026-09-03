import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ModelPerformanceSettingsPage } from './ModelPerformanceSettingsPage'
import * as marketHistoryApi from '../../api/marketHistory'
import type { ForecastAccuracySummary } from '../../types/backend'

function buildSummary(overrides: Partial<ForecastAccuracySummary> = {}): ForecastAccuracySummary {
  return {
    ticker: 'ACME',
    evaluated_count: 3,
    newly_evaluated: 1,
    mean_absolute_error: '4.25',
    mean_percentage_error: '2.10',
    direction_accuracy: '66.7',
    entries: [
      {
        horizon: '30d',
        method: 'lstm',
        prediction_date: '2026-08-01',
        target_date: '2026-08-31',
        predicted_price: '105.00',
        actual_price: '102.50',
        absolute_error: '2.50',
        percentage_error: '2.44',
        direction_correct: true,
      },
    ],
    ...overrides,
  }
}

async function pickTicker(ticker: string) {
  await userEvent.type(screen.getByLabelText(/ticker symbol/i), ticker)
  await userEvent.click(screen.getByRole('button', { name: /view/i }))
}

describe('ModelPerformanceSettingsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('always shows the static, honest Investment Score Performance section', () => {
    render(<ModelPerformanceSettingsPage />)
    expect(screen.getByText(/Score-bucket performance tracking/)).toBeInTheDocument()
    expect(screen.getByText(/Investment Score Performance/)).toBeInTheDocument()
  })

  it('renders real accuracy numbers once a ticker with history is picked', async () => {
    vi.spyOn(marketHistoryApi, 'fetchForecastAccuracy').mockResolvedValue(buildSummary())
    render(<ModelPerformanceSettingsPage />)

    await pickTicker('ACME')

    await waitFor(() => expect(marketHistoryApi.fetchForecastAccuracy).toHaveBeenCalledWith('ACME'))
    expect(await screen.findByText('4.25')).toBeInTheDocument()
    expect(screen.getByText('66.7%')).toBeInTheDocument()
    expect(screen.getByText('lstm')).toBeInTheDocument()
  })

  it('never fabricates a number when there is no backtest history', async () => {
    vi.spyOn(marketHistoryApi, 'fetchForecastAccuracy').mockResolvedValue(
      buildSummary({ evaluated_count: 0, newly_evaluated: 0, mean_absolute_error: null, mean_percentage_error: null, direction_accuracy: null, entries: [] }),
    )
    render(<ModelPerformanceSettingsPage />)

    await pickTicker('NEWCO')

    expect(await screen.findByText(/Accuracy unavailable — insufficient backtest history/)).toBeInTheDocument()
  })

  it('shows insufficient-history text for a null field even when other entries exist', async () => {
    vi.spyOn(marketHistoryApi, 'fetchForecastAccuracy').mockResolvedValue(
      buildSummary({ direction_accuracy: null }),
    )
    render(<ModelPerformanceSettingsPage />)

    await pickTicker('ACME')

    expect(await screen.findByText('insufficient backtest history')).toBeInTheDocument()
  })
})
