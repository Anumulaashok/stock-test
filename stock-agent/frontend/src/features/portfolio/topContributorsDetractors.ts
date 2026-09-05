import type { HoldingWithMarketData } from '../../types/backend'

/** Sorts already-computed holdings by their own `unrealized_gain_percent`
 * (backend-computed, never recomputed here) -- pure selection/sorting,
 * no new statistic derived. A holding with no live price (`null` gain)
 * is excluded from both lists rather than sorted as if it were zero.
 *
 * Contributors are strictly positive-gain holdings, detractors strictly
 * negative -- not just "top N regardless of sign" -- so a holding never
 * appears in both lists at once when the portfolio is small. */
export function topContributors(holdings: HoldingWithMarketData[], count = 3): HoldingWithMarketData[] {
  return holdings
    .filter((h): h is HoldingWithMarketData & { unrealized_gain_percent: string } => h.unrealized_gain_percent !== null && Number(h.unrealized_gain_percent) > 0)
    .sort((a, b) => Number(b.unrealized_gain_percent) - Number(a.unrealized_gain_percent))
    .slice(0, count)
}

export function topDetractors(holdings: HoldingWithMarketData[], count = 3): HoldingWithMarketData[] {
  return holdings
    .filter((h): h is HoldingWithMarketData & { unrealized_gain_percent: string } => h.unrealized_gain_percent !== null && Number(h.unrealized_gain_percent) < 0)
    .sort((a, b) => Number(a.unrealized_gain_percent) - Number(b.unrealized_gain_percent))
    .slice(0, count)
}
