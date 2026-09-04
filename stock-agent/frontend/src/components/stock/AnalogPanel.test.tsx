import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AnalogPanel } from './AnalogPanel'
import type { AnalogSummary } from '../../types/mlForecast'

function base(overrides: Partial<AnalogSummary> = {}): AnalogSummary {
  return {
    sample_size: 0,
    is_reliable: true,
    positive_rate: null,
    negative_rate: null,
    mean_return: null,
    median_return: null,
    quantiles: null,
    ...overrides,
  }
}

describe('AnalogPanel', () => {
  it('renders an empty state when no analogs were found, not a zeroed-out stat block', () => {
    render(<AnalogPanel analog={base()} horizonLabel="14D" />)
    expect(screen.getByText('No historical analogs found')).toBeInTheDocument()
    expect(screen.queryByText('n=0')).not.toBeInTheDocument()
  })

  it('shows both mean and median return, not just one', () => {
    render(
      <AnalogPanel
        analog={base({ sample_size: 18, mean_return: 0.04, median_return: 0.012, positive_rate: 0.6, negative_rate: 0.4 })}
        horizonLabel="1M"
      />,
    )
    expect(screen.getByText('+4.0%')).toBeInTheDocument()
    expect(screen.getByText('+1.2%')).toBeInTheDocument()
  })

  it('visibly desaturates and labels an unreliable analog panel rather than footnoting it', () => {
    const { container } = render(
      <AnalogPanel analog={base({ sample_size: 4, is_reliable: false, mean_return: 0.1, median_return: 0.01 })} horizonLabel="1Y" />,
    )
    expect(screen.getByText(/flagged unreliable by the backend/i)).toBeInTheDocument()
    expect(container.querySelector('.opacity-60')).toBeInTheDocument()
  })

  it('shows sample size adjacent to every figure', () => {
    render(<AnalogPanel analog={base({ sample_size: 31, mean_return: 0.02, median_return: 0.015 })} horizonLabel="3M" />)
    expect(screen.getAllByText('n=31').length).toBeGreaterThanOrEqual(2)
  })

  it('renders a quantile distribution strip when bounding quantiles are present', () => {
    render(
      <AnalogPanel
        analog={base({
          sample_size: 12,
          mean_return: 0.02,
          median_return: 0.01,
          quantiles: { p10: -0.05, p25: -0.01, p50: 0.01, p75: 0.03, p90: 0.08 },
        })}
        horizonLabel="14D"
      />,
    )
    expect(screen.getByText('P10')).toBeInTheDocument()
    expect(screen.getByText('P90')).toBeInTheDocument()
  })
})
