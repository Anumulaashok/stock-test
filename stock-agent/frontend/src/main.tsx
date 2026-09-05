import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/600.css'
import '@fontsource/jetbrains-mono/700.css'
import './index.css'
import { routes } from './routes/routes'
import { AuthProvider } from './auth/AuthContext'

/**
 * `/__dev/ml-panels` -- a fixture gallery for every ML-panel state
 * (empty/degraded/populated), rendered with zero network calls. Dev-only:
 * `import.meta.env.DEV` is statically known at build time, so this whole
 * branch (and the lazy-loaded page module) is dead-code-eliminated from
 * the production bundle, not just hidden behind a runtime check. Kept
 * out of `routes.tsx` (owned by the lead) since it never ships. */
const router = createBrowserRouter(
  import.meta.env.DEV
    ? [
        ...routes,
        {
          path: '__dev/ml-panels',
          lazy: async () => {
            const { MlPanelsFixturePage } = await import('./dev/MlPanelsFixturePage')
            return { Component: MlPanelsFixturePage }
          },
        },
        {
          path: '__dev/health-badge',
          lazy: async () => {
            const { HealthBadgeFixturePage } = await import('./dev/HealthBadgeFixturePage')
            return { Component: HealthBadgeFixturePage }
          },
        },
        {
          path: '__dev/price-chart',
          lazy: async () => {
            const { PriceChartFixturePage } = await import('./dev/PriceChartFixturePage')
            return { Component: PriceChartFixturePage }
          },
        },
        {
          path: '__dev/signal-card',
          lazy: async () => {
            const { SignalCardFixturePage } = await import('./dev/SignalCardFixturePage')
            return { Component: SignalCardFixturePage }
          },
        },
        {
          path: '__dev/forecast-section',
          lazy: async () => {
            const { ForecastSectionFixturePage } = await import('./dev/ForecastSectionFixturePage')
            return { Component: ForecastSectionFixturePage }
          },
        },
        {
          path: '__dev/alerts',
          lazy: async () => {
            const { AlertsFixturePage } = await import('./dev/AlertsFixturePage')
            return { Component: AlertsFixturePage }
          },
        },
        {
          path: '__dev/compare',
          lazy: async () => {
            const { CompareFixturePage } = await import('./dev/CompareFixturePage')
            return { Component: CompareFixturePage }
          },
        },
      ]
    : routes,
)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  </StrictMode>,
)
