import { MarketOpportunity } from '../features/discover/MarketOpportunity'

/** Sector ranking, built from the app's own deterministic scoring --
 * see `features/discover/MarketOpportunity.tsx`. */
export function DiscoverPage() {
  return <MarketOpportunity />
}
