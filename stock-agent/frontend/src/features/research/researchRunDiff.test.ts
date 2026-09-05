import { describe, expect, it } from 'vitest'
import { buildRunDiffRows } from './researchRunDiff'
import { buildReport } from '../../test/fixtures'

describe('buildRunDiffRows', () => {
  it('flags a row as changed only when the two values actually differ', () => {
    const oldReport = buildReport({ summary: { overall_score: '70', overall_status: 'calculated', score_band: 'good', signal: null, investment_thesis: null, key_takeaways: [] } })
    const newReport = buildReport({ summary: { overall_score: '78', overall_status: 'calculated', score_band: 'good', signal: null, investment_thesis: null, key_takeaways: [] } })

    const rows = buildRunDiffRows(oldReport, newReport)
    const scoreRow = rows.find((r) => r.label === 'Overall score')!
    const bandRow = rows.find((r) => r.label === 'Score band')!

    expect(scoreRow).toEqual({ label: 'Overall score', oldValue: '70', newValue: '78', changed: true })
    expect(bandRow.changed).toBe(false)
  })

  it('never computes a delta -- both raw values are shown as-is', () => {
    const oldReport = buildReport({ summary: { overall_score: '70', overall_status: 'calculated', score_band: 'good', signal: null, investment_thesis: null, key_takeaways: [] } })
    const newReport = buildReport({ summary: { overall_score: '78', overall_status: 'calculated', score_band: 'good', signal: null, investment_thesis: null, key_takeaways: [] } })

    const rows = buildRunDiffRows(oldReport, newReport)
    const scoreRow = rows.find((r) => r.label === 'Overall score')!

    expect(scoreRow.oldValue).toBe('70')
    expect(scoreRow.newValue).toBe('78')
    expect(Object.keys(scoreRow)).toEqual(['label', 'oldValue', 'newValue', 'changed'])
  })

  it('counts risk indicators by severity from the arrays already on the report, not a fabricated summary', () => {
    const oldReport = buildReport({
      risk: { source: 'scoring', critical: [], high: [{ name: 'x', severity: 'high', status: 'calculated', value: null, threshold: null, reason: 'elevated' }], medium: [], low: [], informational: [] },
    })
    const newReport = buildReport({
      risk: { source: 'scoring', critical: [], high: [], medium: [], low: [], informational: [] },
    })

    const rows = buildRunDiffRows(oldReport, newReport)
    const riskRow = rows.find((r) => r.label === 'Risk indicators')!

    expect(riskRow.oldValue).toBe('0 critical, 1 high, 0 medium, 0 low')
    expect(riskRow.newValue).toBe('0 critical, 0 high, 0 medium, 0 low')
    expect(riskRow.changed).toBe(true)
  })

  it('handles a null section on either side without throwing', () => {
    const oldReport = buildReport({ market: null, valuation: null, forecast: null, risk: null })
    const newReport = buildReport()

    expect(() => buildRunDiffRows(oldReport, newReport)).not.toThrow()
  })
})
