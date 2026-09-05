import { Navigate, type RouteObject } from 'react-router-dom'
import { AppShell } from '../layouts/AppShell'
import { AuthLayout } from '../layouts/AuthLayout'
import { StockLayout } from '../layouts/StockLayout'
import { SettingsLayout } from '../layouts/SettingsLayout'
import { RequireAuth } from './RequireAuth'
import { RootErrorBoundary } from './RootErrorBoundary'
import { NotFoundPage } from './NotFoundPage'
import { HomePage } from './HomePage'
import { DiscoverPage } from './DiscoverPage'
import { ScreenerPage } from './ScreenerPage'
import { WatchlistPage } from './WatchlistPage'
import { PortfolioPage } from './PortfolioPage'
import { AlertsPage } from './AlertsPage'
import { ComparePage } from './ComparePage'
import { ResearchHistoryPage } from './ResearchHistoryPage'
import { LoginPage } from '../pages/LoginPage'
import { SignupPage } from '../pages/SignupPage'
import { OverviewTab } from './stock/OverviewTab'
import { FundamentalsTab } from './stock/FundamentalsTab'
import { ValuationTab } from './stock/ValuationTab'
import { RiskTab } from './stock/RiskTab'
import { TechnicalTab } from './stock/TechnicalTab'
import { ForecastTab } from './stock/ForecastTab'
import { NewsTab } from './stock/NewsTab'
import { StockResearchTab } from './stock/StockResearchTab'
import { DataSourcesSettingsPage } from './settings/DataSourcesSettingsPage'
import { DataQualitySettingsPage } from './settings/DataQualitySettingsPage'
import { ModelPerformanceSettingsPage } from './settings/ModelPerformanceSettingsPage'
import { SystemSettingsPage } from './settings/SystemSettingsPage'

/**
 * The single route tree -- every page in the app registers here, and
 * every link in the app goes through `paths.ts` rather than a literal
 * string, so the two can never drift apart. Owned exclusively by the
 * lead; a workstream adding a page hands back a one-line addition here
 * rather than editing this file itself, to avoid merge collisions
 * across parallel agents.
 */
export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppShell />,
    errorElement: <RootErrorBoundary />,
    children: [
      { index: true, element: <HomePage />, handle: { crumb: () => 'Intelligence' } },
      { path: 'discover', element: <DiscoverPage />, handle: { crumb: () => 'Discover' } },
      { path: 'screener', element: <ScreenerPage />, handle: { crumb: () => 'Screener' } },

      {
        path: 'stock/:ticker',
        element: <StockLayout />,
        handle: { crumb: (params: Record<string, string | undefined>) => params.ticker ?? 'Stock' },
        children: [
          { index: true, element: <OverviewTab /> },
          { path: 'fundamentals', element: <FundamentalsTab /> },
          { path: 'valuation', element: <ValuationTab /> },
          { path: 'risk', element: <RiskTab /> },
          { path: 'technical', element: <TechnicalTab /> },
          { path: 'forecast', element: <ForecastTab /> },
          { path: 'news', element: <NewsTab /> },
          { path: 'research', element: <StockResearchTab /> },
        ],
      },

      { path: 'research', element: <ResearchHistoryPage />, handle: { crumb: () => 'Research' } },
      { path: 'compare', element: <ComparePage />, handle: { crumb: () => 'Compare' } },

      {
        element: <RequireAuth />,
        children: [
          { path: 'watchlist', element: <WatchlistPage />, handle: { crumb: () => 'Watchlist' } },
          { path: 'portfolio', element: <PortfolioPage />, handle: { crumb: () => 'Portfolio' } },
          { path: 'alerts', element: <AlertsPage />, handle: { crumb: () => 'Alerts' } },
          {
            path: 'settings',
            element: <SettingsLayout />,
            handle: { crumb: () => 'Settings' },
            children: [
              { index: true, element: <Navigate to="data-sources" replace /> },
              { path: 'data-sources', element: <DataSourcesSettingsPage /> },
              { path: 'data-quality', element: <DataQualitySettingsPage /> },
              { path: 'model-performance', element: <ModelPerformanceSettingsPage /> },
              { path: 'system', element: <SystemSettingsPage /> },
            ],
          },
        ],
      },

      { path: '*', element: <NotFoundPage /> },
    ],
  },
  {
    element: <AuthLayout />,
    children: [
      { path: 'login', element: <LoginPage /> },
      { path: 'signup', element: <SignupPage /> },
    ],
  },
]
