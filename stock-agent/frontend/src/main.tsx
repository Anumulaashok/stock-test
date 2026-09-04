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
