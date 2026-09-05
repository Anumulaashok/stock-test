import { describe, expect, it } from 'vitest'
import { calculatePositionSize } from './positionSize'

describe('calculatePositionSize', () => {
  it('computes share count as risk amount divided by per-share risk, floored', () => {
    // Account 100000, risk 1% => risk amount 1000. Entry 100, stop 90 => per-share risk 10. 1000/10 = 100 shares.
    const result = calculatePositionSize({ accountSize: 100000, riskPercent: 1, entryPrice: 100, stopPrice: 90 })
    expect(result).toEqual({ shareCount: 100, positionValue: 10000, riskAmount: 1000 })
  })

  it('floors a fractional share count rather than rounding up past the risk budget', () => {
    const result = calculatePositionSize({ accountSize: 1000, riskPercent: 1, entryPrice: 100, stopPrice: 97 })
    // risk amount 10, per-share risk 3 -> 3.33 shares -> floors to 3
    expect(result?.shareCount).toBe(3)
  })

  it('treats a stop above the entry the same as below -- risk is a distance, not a direction', () => {
    const long = calculatePositionSize({ accountSize: 100000, riskPercent: 1, entryPrice: 100, stopPrice: 90 })
    const short = calculatePositionSize({ accountSize: 100000, riskPercent: 1, entryPrice: 90, stopPrice: 100 })
    expect(short?.shareCount).toBe(long?.shareCount)
  })

  it('returns null when entry equals stop -- an undefined per-share risk, never a divide-by-zero', () => {
    expect(calculatePositionSize({ accountSize: 100000, riskPercent: 1, entryPrice: 100, stopPrice: 100 })).toBeNull()
  })

  it('returns null for a non-positive account size, risk percent, or price', () => {
    expect(calculatePositionSize({ accountSize: 0, riskPercent: 1, entryPrice: 100, stopPrice: 90 })).toBeNull()
    expect(calculatePositionSize({ accountSize: 100000, riskPercent: 0, entryPrice: 100, stopPrice: 90 })).toBeNull()
    expect(calculatePositionSize({ accountSize: 100000, riskPercent: 1, entryPrice: -100, stopPrice: 90 })).toBeNull()
    expect(calculatePositionSize({ accountSize: 100000, riskPercent: 1, entryPrice: 100, stopPrice: -90 })).toBeNull()
  })
})
