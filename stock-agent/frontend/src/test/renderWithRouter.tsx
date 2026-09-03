import { render, type RenderOptions } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'

/** Wraps a component under test in a `MemoryRouter` -- for components
 * that render `<Link>`/`<NavLink>` but don't need a full route tree
 * (use `renderRoute` from `renderRoute.tsx` for that instead). */
export function renderWithRouter(ui: ReactElement, options?: RenderOptions & { initialEntries?: string[] }) {
  const { initialEntries = ['/'], ...renderOptions } = options ?? {}
  return render(<MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>, renderOptions)
}
