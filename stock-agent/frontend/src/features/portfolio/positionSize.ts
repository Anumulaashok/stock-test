export interface PositionSizeInputs {
  accountSize: number
  riskPercent: number
  entryPrice: number
  stopPrice: number
}

export interface PositionSizeResult {
  shareCount: number
  positionValue: number
  riskAmount: number
}

/**
 * Arithmetic over user-tuned inputs and a real quote -- explicitly
 * permitted (I3: "A position-size calculator is permitted -- arithmetic
 * over user input and a real quote"). Every output is SCENARIO-badged
 * by the caller (I11); this never produces a buy/sell affordance, only
 * a share count and its dollar/rupee size.
 *
 * `null` for any input that would make the arithmetic meaningless
 * (non-positive size/risk/price, or entry == stop, which is an
 * undefined per-share risk) -- never a divide-by-zero or a fabricated
 * number.
 */
export function calculatePositionSize({ accountSize, riskPercent, entryPrice, stopPrice }: PositionSizeInputs): PositionSizeResult | null {
  if (!(accountSize > 0) || !(riskPercent > 0) || !(entryPrice > 0) || !(stopPrice > 0)) return null
  const perShareRisk = Math.abs(entryPrice - stopPrice)
  if (perShareRisk === 0) return null

  const riskAmount = accountSize * (riskPercent / 100)
  const shareCount = Math.floor(riskAmount / perShareRisk)
  const positionValue = shareCount * entryPrice
  return { shareCount, positionValue, riskAmount }
}
