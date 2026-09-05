import { describe, expect, it } from 'vitest'
import { buildFinancialMetricRows, buildRiskRows, buildSummaryRows, buildValuationRows } from './compareRows'
import { buildReport } from '../../test/fixtures'

describe('buildSummaryRows', () => {
  it('highlights the highest score as best and the lowest as worst', () => {
    const a = buildReport({ summary: { overall_score: '80', overall_status: 'calculated', score_band: 'good', signal: null, investment_thesis: null, key_takeaways: [] } })
    const b = buildReport({ summary: { overall_score: '60', overall_status: 'calculated', score_band: 'fair', signal: null, investment_thesis: null, key_takeaways: [] } })

    const rows = buildSummaryRows([a, b], ['A', 'B'])
    const scoreRow = rows.find((r) => r.label === 'Overall score')!

    expect(scoreRow.bestTicker).toBe('A')
    expect(scoreRow.worstTicker).toBe('B')
  })

  it('never picks a best/worst ticker for a null report -- shows unavailable instead', () => {
    const a = buildReport({ summary: { overall_score: '80', overall_status: 'calculated', score_band: 'good', signal: null, investment_thesis: null, key_takeaways: [] } })
    const rows = buildSummaryRows([a, null], ['A', 'B'])
    const scoreRow = rows.find((r) => r.label === 'Overall score')!

    expect(scoreRow.cells[1].formattedValue).toBeNull()
    expect(scoreRow.bestTicker).toBeNull()
    expect(scoreRow.worstTicker).toBeNull()
  })

  it('does not pick a best/worst ticker for band or signal rows -- no established direction', () => {
    const a = buildReport()
    const rows = buildSummaryRows([a, a], ['A', 'B'])
    expect(rows.find((r) => r.label === 'Band')!.bestTicker).toBeNull()
    expect(rows.find((r) => r.label === 'Signal')!.bestTicker).toBeNull()
  })

  it('ties never produce a best or worst', () => {
    const a = buildReport({ summary: { overall_score: '70', overall_status: 'calculated', score_band: 'good', signal: null, investment_thesis: null, key_takeaways: [] } })
    const rows = buildSummaryRows([a, a], ['A', 'B'])
    const scoreRow = rows.find((r) => r.label === 'Overall score')!
    expect(scoreRow.bestTicker).toBeNull()
    expect(scoreRow.worstTicker).toBeNull()
  })
})

describe('buildValuationRows', () => {
  it('unions method names across reports -- a ticker missing a method still gets a row with unavailable', () => {
    const a = buildReport({
      valuation: { source: 'valuation', current_share_price: '100', formatted_current_share_price: '$100', methods: [
        { method: 'dcf', value_per_share: '140', status: 'calculated', reason: null, upside_downside_percent: '40', upside_downside_status: 'calculated', assumptions: {}, formatted_value_per_share: '$140', formatted_upside_downside: '+40%' },
      ] },
    })
    const b = buildReport({ valuation: { source: 'valuation', current_share_price: '50', formatted_current_share_price: '$50', methods: [] } })

    const rows = buildValuationRows([a, b], ['A', 'B'])
    expect(rows).toHaveLength(1)
    expect(rows[0].cells[1].formattedValue).toBeNull()
  })

  it('picks the higher upside as best for the same method', () => {
    const a = buildReport({
      valuation: { source: 'valuation', current_share_price: '100', formatted_current_share_price: '$100', methods: [
        { method: 'dcf', value_per_share: '140', status: 'calculated', reason: null, upside_downside_percent: '40', upside_downside_status: 'calculated', assumptions: {}, formatted_value_per_share: '$140', formatted_upside_downside: '+40%' },
      ] },
    })
    const b = buildReport({
      valuation: { source: 'valuation', current_share_price: '50', formatted_current_share_price: '$50', methods: [
        { method: 'dcf', value_per_share: '55', status: 'calculated', reason: null, upside_downside_percent: '10', upside_downside_status: 'calculated', assumptions: {}, formatted_value_per_share: '$55', formatted_upside_downside: '+10%' },
      ] },
    })

    const rows = buildValuationRows([a, b], ['A', 'B'])
    expect(rows[0].bestTicker).toBe('A')
    expect(rows[0].worstTicker).toBe('B')
  })
})

describe('buildFinancialMetricRows', () => {
  it('never assigns a best/worst ticker -- directionality is ambiguous per metric', () => {
    const a = buildReport()
    const rows = buildFinancialMetricRows([a, a], ['A', 'B'])
    expect(rows.every((r) => r.bestTicker === null && r.worstTicker === null)).toBe(true)
  })

  it('unions metric names across profitability/growth/health/cash-flow', () => {
    const a = buildReport()
    const rows = buildFinancialMetricRows([a], ['A'])
    expect(rows.some((r) => r.label.toLowerCase().includes('roe'))).toBe(true)
  })
})

describe('buildRiskRows', () => {
  it('reshapes risk-indicator array lengths, never a computed statistic', () => {
    const a = buildReport({
      risk: { source: 'scoring', critical: [], high: [{ name: 'x', severity: 'high', status: 'calculated', value: null, threshold: null, reason: 'r' }], medium: [], low: [], informational: [] },
    })
    const rows = buildRiskRows([a], ['A'])
    expect(rows.find((r) => r.label === 'High risk indicators')!.cells[0].formattedValue).toBe('1')
  })

  it('shows unavailable, not zero, when risk is null', () => {
    const a = buildReport({ risk: null })
    const rows = buildRiskRows([a], ['A'])
    expect(rows[0].cells[0].formattedValue).toBeNull()
  })
})
