import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { AskAssistantSection } from './AskAssistantSection'
import { ApiError } from '../api/client'
import * as qaApi from '../api/qa'
import type { QAResult } from '../types/backend'

const EMPTY_EVIDENCE = { financial: [], valuation: [], risk: [], research: [] }

async function ask(question: string) {
  await userEvent.type(screen.getByLabelText(/ask a question/i), question)
  await userEvent.click(screen.getByRole('button', { name: /ask/i }))
}

describe('AskAssistantSection', () => {
  it('submits a question and renders the answer with evidence', async () => {
    const result: QAResult = {
      status: 'success',
      response: {
        answer: 'ROE is calculated at 24%.',
        evidence: { ...EMPTY_EVIDENCE, financial: ['roe'] },
        recommendation_declined: false,
      },
      error: null,
    }
    vi.spyOn(qaApi, 'askTickerQuestion').mockResolvedValue(result)

    render(<AskAssistantSection ticker="ACME" />)
    await ask('How is profitability?')

    expect(await screen.findByText('ROE is calculated at 24%.')).toBeInTheDocument()
    expect(qaApi.askTickerQuestion).toHaveBeenCalledWith('ACME', 'How is profitability?')

    await userEvent.click(screen.getByRole('button', { name: /why does the assistant say this/i }))
    expect(screen.getByText('Roe')).toBeInTheDocument()
  })

  it('shows a note when the assistant declines to give a recommendation', async () => {
    const result: QAResult = {
      status: 'success',
      response: {
        answer: "This assistant doesn't give buy/sell recommendations. ROE is 24%.",
        evidence: EMPTY_EVIDENCE,
        recommendation_declined: true,
      },
      error: null,
    }
    vi.spyOn(qaApi, 'askTickerQuestion').mockResolvedValue(result)

    render(<AskAssistantSection ticker="ACME" />)
    await ask('Should I buy this stock?')

    await waitFor(() => expect(screen.getByText(/doesn't give buy\/sell\/hold recommendations/i)).toBeInTheDocument())
  })

  it('shows an error message when the backend returns a structured error', async () => {
    const result: QAResult = {
      status: 'error',
      response: null,
      error: { code: 'llm_unavailable', message: 'The assistant is temporarily unavailable.' },
    }
    vi.spyOn(qaApi, 'askTickerQuestion').mockResolvedValue(result)

    render(<AskAssistantSection ticker="ACME" />)
    await ask('How is profitability?')

    expect(await screen.findByText('The assistant is temporarily unavailable.')).toBeInTheDocument()
  })

  it('shows a friendly message on a network failure', async () => {
    vi.spyOn(qaApi, 'askTickerQuestion').mockRejectedValue(new ApiError('boom', 'network'))

    render(<AskAssistantSection ticker="ACME" />)
    await ask('How is profitability?')

    expect(await screen.findByText(/could not reach the server/i)).toBeInTheDocument()
  })
})
