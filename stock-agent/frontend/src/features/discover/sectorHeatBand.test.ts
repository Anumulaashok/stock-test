import { describe, expect, it } from 'vitest'
import { sectorHeatBand } from './sectorHeatBand'

describe('sectorHeatBand', () => {
  it('returns unavailable for a null score', () => {
    expect(sectorHeatBand(null)).toBe('unavailable')
  })

  it('returns strong at and above 70', () => {
    expect(sectorHeatBand('70')).toBe('strong')
    expect(sectorHeatBand('95')).toBe('strong')
  })

  it('returns neutral between 45 and 69', () => {
    expect(sectorHeatBand('45')).toBe('neutral')
    expect(sectorHeatBand('69')).toBe('neutral')
  })

  it('returns weak below 45', () => {
    expect(sectorHeatBand('44')).toBe('weak')
    expect(sectorHeatBand('0')).toBe('weak')
  })

  it('returns unavailable for a non-numeric string, never a fabricated band', () => {
    expect(sectorHeatBand('not-a-number')).toBe('unavailable')
  })
})
