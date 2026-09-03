import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DataQualitySettingsPage } from './DataQualitySettingsPage'
import * as researchApi from '../../api/research'
import { buildReport, buildRunResult } from '../../test/fixtures'

async function pickTicker(ticker: string) {
  await userEvent.type(screen.getByLabelText(/ticker symbol/i), ticker)
  await userEvent.click(screen.getByRole('button', { name: /view/i }))
}

describe('DataQualitySettingsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('does not fetch anything before a ticker is chosen', () => {
    const spy = vi.spyOn(researchApi, 'fetchLatestResearch')
    render(<DataQualitySettingsPage />)
    expect(screen.getByText(/enter a ticker/i)).toBeInTheDocument()
    expect(spy).not.toHaveBeenCalled()
  })

  it('renders DataQualitySection for the picked ticker', async () => {
    vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(buildRunResult(buildReport()))
    render(<DataQualitySettingsPage />)

    await pickTicker('ACME')

    await waitFor(() => expect(researchApi.fetchLatestResearch).toHaveBeenCalledWith('ACME'))
    expect(await screen.findByText(/metrics evaluated/)).toBeInTheDocument()
  })

  it('shows an honest empty state when nothing has been researched yet', async () => {
    vi.spyOn(researchApi, 'fetchLatestResearch').mockResolvedValue(null)
    render(<DataQualitySettingsPage />)

    await pickTicker('NEWCO')

    expect(await screen.findByText(/No research has been run for NEWCO yet/)).toBeInTheDocument()
  })

  it('surfaces a retryable error instead of a fake report', async () => {
    vi.spyOn(researchApi, 'fetchLatestResearch').mockRejectedValue(new Error('network'))
    render(<DataQualitySettingsPage />)

    await pickTicker('ACME')

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
