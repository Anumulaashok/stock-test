import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { routes } from '../routes/routes'
import { renderRoute } from '../test/renderRoute'
import { buildReport, buildRunResult } from '../test/fixtures'
import * as researchApi from '../api/research'
import * as portfolioApi from '../api/portfolio'
import { ApiError } from '../api/client'

/**
 * The load-bearing test for the redesign's single architectural
 * decision: `/stock/:ticker` fetches its report exactly once and every
 * tab reads it from context, so switching tabs never refetches.
 */
describe('StockLayout', () => {
  beforeEach(() => {
    vi.spyOn(portfolioApi, 'fetchWatchlist').mockResolvedValue([])
  })

  it('fetches the report once and never again across tab navigation', async () => {
    const fetchLatest = vi
      .spyOn(researchApi, 'fetchLatestResearch')
      .mockResolvedValue(buildRunResult(buildReport({ company: { name: 'Acme Corp', ticker: 'ACME', currency: null } })))

    renderRoute(routes, '/stock/ACME')

    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: /acme corp/i })).toBeInTheDocument())
    expect(fetchLatest).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('link', { name: 'Fundamentals' }))
    await waitFor(() => expect(screen.getByRole('link', { name: 'Fundamentals' })).toHaveAttribute('aria-current', 'page'))

    await userEvent.click(screen.getByRole('link', { name: 'Risk' }))
    await waitFor(() => expect(screen.getByRole('link', { name: 'Risk' })).toHaveAttribute('aria-current', 'page'))

    expect(fetchLatest).toHaveBeenCalledTimes(1)
  })

  it('shows an empty state on a 404 and never auto-runs research', async () => {
    vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(null)
    const runResearchSpy = vi.spyOn(researchApi, 'runResearch')

    renderRoute(routes, '/stock/NEWCO')

    await waitFor(() => expect(screen.getByText(/hasn't been researched yet/i)).toBeInTheDocument())
    expect(runResearchSpy).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /run research/i })).toBeInTheDocument()
  })

  it('redirects a lowercase ticker to its uppercase URL', async () => {
    vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(
      buildRunResult(buildReport({ company: { name: 'Acme Corp', ticker: 'ACME', currency: null } })),
    )

    const { router } = renderRoute(routes, '/stock/acme')

    await waitFor(() => expect(router.state.location.pathname).toBe('/stock/ACME'))
  })

  it('loads a specific historical run when ?run= is present, and tab links preserve it', async () => {
    vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(
      buildRunResult(buildReport({ company: { name: 'Acme Corp', ticker: 'ACME', currency: null } })),
    )
    const fetchRun = vi
      .spyOn(researchApi, 'fetchResearchRun')
      .mockResolvedValue(buildRunResult(buildReport({ company: { name: 'Acme Corp (past)', ticker: 'ACME', currency: null } })))

    renderRoute(routes, '/stock/ACME?run=run-42')

    await waitFor(() => expect(fetchRun).toHaveBeenCalledWith('ACME', 'run-42'))
    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: /acme corp \(past\)/i })).toBeInTheDocument())

    const fundamentalsLink = screen.getByRole('link', { name: 'Fundamentals' })
    expect(fundamentalsLink).toHaveAttribute('href', expect.stringContaining('run=run-42'))
  })

  it('shows a retry affordance, not a dead-end banner, on a 409 (research already running)', async () => {
    vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(null)
    vi.spyOn(researchApi, 'runResearch').mockRejectedValue(
      new ApiError('Research for ACME on 2026-09-04 is already in progress in another request.', 'client', 409),
    )

    renderRoute(routes, '/stock/ACME')
    await waitFor(() => expect(screen.getByRole('button', { name: /run research/i })).toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: /run research/i }))

    await waitFor(() => expect(screen.getByText(/already running for ACME/i)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /check again/i })).toBeInTheDocument()
  })
})
