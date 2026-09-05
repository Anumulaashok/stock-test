import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { NewsImpactPanel } from './NewsImpactPanel'
import type { NewsImpactSection } from '../../types/mlForecast'

function base(overrides: Partial<NewsImpactSection> = {}): NewsImpactSection {
  return {
    recent_events: [],
    historical_statistics: [],
    data_available: true,
    note: null,
    ...overrides,
  }
}

describe('NewsImpactPanel', () => {
  it('renders data_available: false as a stated condition with the backend note shown verbatim', () => {
    render(<NewsImpactPanel newsImpact={base({ data_available: false, note: 'No news provider configured for this deployment.' })} />)
    expect(screen.getByText('News-derived signals unavailable')).toBeInTheDocument()
    expect(screen.getByText('No news provider configured for this deployment.')).toBeInTheDocument()
  })

  it('separates recent events from historical statistics into distinct labeled sections', () => {
    render(
      <NewsImpactPanel
        newsImpact={base({
          recent_events: [
            {
              headline: 'Company announces earnings beat',
              published_at: '2026-08-20T10:00:00+00:00',
              event_type: 'earnings',
              sentiment: 'POSITIVE',
              market_timing: 'pre_market',
              url: null,
            },
          ],
          historical_statistics: [
            {
              event_type: 'earnings',
              sample_size: 23,
              is_reliable: true,
              median_return_5d: 0.021,
              median_return_14d: 0.034,
              positive_rate_5d: 0.65,
              positive_rate_14d: 0.7,
            },
          ],
        })}
      />,
    )

    expect(screen.getByText('Recent events')).toBeInTheDocument()
    expect(screen.getByText('Past reaction by event type -- not a projection')).toBeInTheDocument()
    expect(screen.getByText('Company announces earnings beat')).toBeInTheDocument()
    expect(screen.getByText('n=23')).toBeInTheDocument()
    expect(screen.getByText(/\+2\.1%/)).toBeInTheDocument()
  })

  it('never attaches an event-study statistic to a specific recent headline as its expected move', () => {
    render(
      <NewsImpactPanel
        newsImpact={base({
          recent_events: [
            { headline: 'Regulatory probe announced', published_at: '2026-08-20T10:00:00+00:00', event_type: 'regulatory', sentiment: 'NEGATIVE', market_timing: 'intraday', url: null },
          ],
          historical_statistics: [
            { event_type: 'regulatory', sample_size: 9, is_reliable: false, median_return_5d: -0.015, median_return_14d: null, positive_rate_5d: 0.33, positive_rate_14d: null },
          ],
        })}
      />,
    )

    const headlineItem = screen.getByText('Regulatory probe announced').closest('li')
    expect(headlineItem?.textContent).not.toMatch(/-1\.5%/)
    expect(screen.getByText('Flagged unreliable by the backend -- small or noisy sample.')).toBeInTheDocument()
  })

  it('renders sentiment as a plain uncolored tag, never a green/red recommendation-style badge', () => {
    render(
      <NewsImpactPanel
        newsImpact={base({
          recent_events: [
            { headline: 'Strong quarter reported', published_at: '2026-08-20T10:00:00+00:00', event_type: 'earnings', sentiment: 'POSITIVE', market_timing: 'pre_market', url: null },
          ],
        })}
      />,
    )
    const tag = screen.getByText('POSITIVE sentiment')
    expect(tag.className).not.toMatch(/green|status-positive/i)
  })
})
