import { useState } from 'react'
import { askTickerQuestion } from '../api/qa'
import { ApiError } from '../api/client'
import type { AnalystEvidence } from '../types/backend'
import { humanizeKey } from '../lib/format'

interface Turn {
  question: string
  status: 'loading' | 'answered' | 'error'
  answer?: string
  evidence?: AnalystEvidence
  recommendationDeclined?: boolean
  errorMessage?: string
}

const FRIENDLY_MESSAGE: Record<ApiError['kind'], string> = {
  network: 'Could not reach the server. Check your connection and try again.',
  timeout: 'The request took too long and was cancelled. Please try again.',
  client: 'The request could not be processed.',
  server: 'The assistant encountered an unexpected error. Please try again shortly.',
}

function EvidenceDisclosure({ evidence, id }: { evidence: AnalystEvidence; id: string }) {
  const [open, setOpen] = useState(false)
  const entries = (['financial', 'valuation', 'risk', 'research'] as const).flatMap((namespace) =>
    evidence[namespace].map((name) => ({ namespace, name })),
  )
  if (entries.length === 0) return null

  return (
    <div className="mt-1.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={id}
        className="text-xs font-medium text-[var(--color-accent)] underline-offset-2 hover:underline"
      >
        {open ? 'Hide evidence' : 'Why does the assistant say this?'}
      </button>
      {open && (
        <ul id={id} className="mt-1 flex flex-wrap gap-1.5">
          {entries.map(({ namespace, name }) => (
            <li
              key={`${namespace}-${name}`}
              className="rounded border border-[var(--color-border)] bg-[var(--color-accent-soft)] px-1.5 py-0.5 text-xs"
              title={`${humanizeKey(namespace)} evidence`}
            >
              {humanizeKey(name)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * Free-form Q&A over the deterministic analysis for `ticker`. This never
 * issues a buy/sell/hold recommendation or a price-probability estimate
 * (see app/qa/prompts.py) -- when a question asks for one, the backend
 * declines and explains the relevant evidence instead, surfaced here via
 * `recommendationDeclined`.
 */
export function AskAssistantSection({ ticker }: { ticker: string }) {
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const busy = turns.some((t) => t.status === 'loading')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || busy) return

    setQuestion('')
    setTurns((prev) => [...prev, { question: trimmed, status: 'loading' }])

    try {
      const result = await askTickerQuestion(ticker, trimmed)
      setTurns((prev) =>
        prev.map((t, i) =>
          i === prev.length - 1
            ? result.status === 'success' && result.response
              ? {
                  ...t,
                  status: 'answered',
                  answer: result.response.answer,
                  evidence: result.response.evidence,
                  recommendationDeclined: result.response.recommendation_declined,
                }
              : { ...t, status: 'error', errorMessage: result.error?.message }
            : t,
        ),
      )
    } catch (error) {
      const apiError = error instanceof ApiError ? error : new ApiError('Unexpected error.', 'network')
      setTurns((prev) =>
        prev.map((t, i) =>
          i === prev.length - 1 ? { ...t, status: 'error', errorMessage: FRIENDLY_MESSAGE[apiError.kind] } : t,
        ),
      )
    }
  }

  return (
    <section aria-labelledby="ask-assistant-heading" className="surface-card space-y-4 p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="ask-assistant-heading" className="section-heading">
          Ask the Assistant
        </h2>
        <span className="text-xs text-[var(--color-text-faint)]">
          Answers evidence, no buy/sell/hold calls or price predictions
        </span>
      </div>

      {turns.length > 0 && (
        <ul className="space-y-4">
          {turns.map((turn, i) => (
            <li key={i} className="border-l-2 border-[var(--color-border)] pl-3">
              <p className="text-sm font-semibold">{turn.question}</p>
              {turn.status === 'loading' && (
                <p className="mt-1 text-sm text-[var(--color-text-faint)]">Thinking…</p>
              )}
              {turn.status === 'error' && (
                <p className="mt-1 text-sm text-[var(--color-status-critical)]">
                  {turn.errorMessage || 'The assistant could not answer that question.'}
                </p>
              )}
              {turn.status === 'answered' && (
                <div className="mt-1">
                  {turn.recommendationDeclined && (
                    <p className="mb-1 text-xs italic text-[var(--color-text-faint)]">
                      This assistant doesn't give buy/sell/hold recommendations or price predictions -- here's
                      what the evidence shows instead.
                    </p>
                  )}
                  <p className="text-sm leading-relaxed text-[var(--color-text-muted)]">{turn.answer}</p>
                  {turn.evidence && <EvidenceDisclosure evidence={turn.evidence} id={`qa-evidence-${i}`} />}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="qa-question" className="sr-only">
          Ask a question about this company
        </label>
        <input
          id="qa-question"
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about this company's evidence, e.g. how is its profitability?"
          disabled={busy}
          className="input-field flex-1 px-3.5 py-2.5 text-sm"
        />
        <button
          type="submit"
          disabled={busy || !question.trim()}
          className="btn-primary shrink-0 px-5 py-2.5 text-sm"
        >
          Ask
        </button>
      </form>
    </section>
  )
}
