import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router-dom'
import { render } from '@testing-library/react'
import { AuthProvider } from '../auth/AuthContext'
import { ThemeProvider } from '../theme/ThemeContext'

/** Renders a route tree at a given path -- for route-level tests
 * (redirects, layout routes, nested tabs) rather than a single
 * component in isolation. Every test importing this needs the router
 * mounted the same way the real app does, plus auth and theme context. */
export function renderRoute(routes: RouteObject[], initialPath: string) {
  const router = createMemoryRouter(routes, { initialEntries: [initialPath] })
  return {
    router,
    ...render(
      <ThemeProvider>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </ThemeProvider>,
    ),
  }
}
