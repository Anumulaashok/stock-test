/**
 * The single source of truth for every URL in the app. No route string
 * literal should appear anywhere outside this file and `routes.tsx` --
 * every link/redirect goes through these builders so a path can never
 * drift from what `routes.tsx` actually registers.
 */

export const STOCK_TABS = [
  { segment: '', label: 'Overview' },
  { segment: 'fundamentals', label: 'Fundamentals' },
  { segment: 'valuation', label: 'Valuation' },
  { segment: 'risk', label: 'Risk' },
  { segment: 'technical', label: 'Technical' },
  { segment: 'forecast', label: 'Forecast' },
  { segment: 'news', label: 'News' },
  { segment: 'research', label: 'Research' },
] as const

export type StockTabSegment = (typeof STOCK_TABS)[number]['segment']

export const paths = {
  home: () => '/',
  discover: () => '/discover',
  watchlist: () => '/watchlist',
  portfolio: () => '/portfolio',
  research: () => '/research',
  stock: (ticker: string) => `/stock/${encodeURIComponent(ticker)}`,
  stockTab: (ticker: string, tab: StockTabSegment) =>
    tab ? `/stock/${encodeURIComponent(ticker)}/${tab}` : `/stock/${encodeURIComponent(ticker)}`,
  settings: (section: 'data-sources' | 'data-quality' | 'model-performance' | 'system' = 'data-sources') =>
    `/settings/${section}`,
  login: () => '/login',
  signup: () => '/signup',
} as const
