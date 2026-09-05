import { render, type RenderOptions } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../theme/ThemeContext'

/** Wraps a component under test in a `MemoryRouter` -- for components
 * that render `<Link>`/`<NavLink>` but don't need a full route tree
 * (use `renderRoute` from `renderRoute.tsx` for that instead). Also
 * wraps in `ThemeProvider` -- unlike auth status, theme has no
 * per-test variants worth mocking, so every caller gets a real one. */
export function renderWithRouter(ui: ReactElement, options?: RenderOptions & { initialEntries?: string[] }) {
  const { initialEntries = ['/'], ...renderOptions } = options ?? {}
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </ThemeProvider>,
    renderOptions,
  )
}
