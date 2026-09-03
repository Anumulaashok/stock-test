import { useEffect, useRef, useState } from 'react'
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

const SUGGESTED_QUESTIONS = [
  'How is profitability trending?',
  "What's driving the valuation?",
  'Any major risks to know about?',
]

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
        className="text-[11px] font-medium text-[var(--color-accent)] underline-offset-2 hover:underline"
      >
        {open ? 'Hide evidence' : 'Why does the assistant say this?'}
      </button>
      {open && (
        <ul id={id} className="mt-1 flex flex-wrap gap-1.5">
          {entries.map(({ namespace, name }) => (
            <li
              key={`${namespace}-${name}`}
              className="rounded border border-[var(--color-border)] bg-[var(--color-accent-soft)] px-1.5 py-0.5 text-[11px]"
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
 * Premium floating "Ask Stock Agent" assistant, docked bottom-right and
 * always accessible while scrolling -- functionally identical Q&A over
 * the deterministic analysis (see `app/qa/prompts.py`: never a buy/sell
 * recommendation or price estimate) as the old inline `AskAssistantSection`,
 * just redesigned as a compact/expandable sticky panel instead of a
 * page section.
 */
export function StickyAskAssistant({ ticker }: { ticker: string | null }) {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const listRef = useRef<HTMLUListElement>(null)
  const busy = turns.some((t) => t.status === 'loading')

  // A new ticker means the conversation no longer applies to what's on
  // screen -- start fresh rather than mixing Q&A across tickers.
  useEffect(() => {
    setTurns([])
    setQuestion('')
  }, [ticker])

  useEffect(() => {
    const el = listRef.current
    if (el && typeof el.scrollTo === 'function') {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  }, [turns])

  async function submitQuestion(raw: string) {
    const trimmed = raw.trim()
    if (!trimmed || busy || !ticker) return

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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    void submitQuestion(question)
  }

  return (
    <div className="pointer-events-none fixed bottom-5 right-4 z-30 flex flex-col items-end sm:bottom-6 sm:right-6">
      <div
        className={
          'mb-3 w-[calc(100vw-2rem)] max-w-[380px] origin-bottom-right overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] shadow-[0_16px_48px_rgba(0,0,0,0.18)] transition-all duration-200 ease-out ' +
          (open ? 'pointer-events-auto max-h-[32rem] translate-y-0 scale-100 opacity-100' : 'pointer-events-none max-h-0 translate-y-2 scale-95 opacity-0')
        }
        aria-hidden={!open}
      >
        <div className="flex items-center justify-between gap-2 border-b border-[var(--color-border)] bg-gradient-to-r from-[var(--color-accent-soft)] to-transparent px-4 py-3">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-sm font-semibold text-[var(--color-text)]">
              <span aria-hidden className="text-[var(--color-accent)]">✦</span>
              Ask Stock Agent
            </div>
            <p className="truncate text-[11px] text-[var(--color-text-faint)]">
              {ticker ? `Grounded on ${ticker}'s research` : 'Search a ticker to start asking'}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Collapse assistant"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[var(--color-text-faint)] transition-colors hover:bg-[var(--color-border)]/50 hover:text-[var(--color-text)]"
          >
            ×
          </button>
        </div>

        {ticker ? (
          <>
            <ul ref={listRef} className="flex max-h-64 flex-col gap-3 overflow-y-auto px-4 py-3">
              {turns.length === 0 && (
                <li className="flex flex-wrap gap-1.5">
                  {SUGGESTED_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => void submitQuestion(q)}
                      className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1 text-[11px] font-medium text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-accent)]/40 hover:text-[var(--color-accent-strong)]"
                    >
                      {q}
                    </button>
                  ))}
                </li>
              )}
              {turns.map((turn, i) => (
                <li key={i} className="border-l-2 border-[var(--color-border)] pl-2.5">
                  <p className="text-xs font-semibold text-[var(--color-text)]">{turn.question}</p>
                  {turn.status === 'loading' && (
                    <p className="mt-1 text-xs text-[var(--color-text-faint)]">Thinking…</p>
                  )}
                  {turn.status === 'error' && (
                    <p className="mt-1 text-xs text-[var(--color-status-critical)]">
                      {turn.errorMessage || 'The assistant could not answer that question.'}
                    </p>
                  )}
                  {turn.status === 'answered' && (
                    <div className="mt-1">
                      {turn.recommendationDeclined && (
                        <p className="mb-1 text-[11px] italic text-[var(--color-text-faint)]">
                          No buy/sell/hold calls or price predictions -- here's what the evidence shows instead.
                        </p>
                      )}
                      <p className="text-xs leading-relaxed text-[var(--color-text-muted)]">{turn.answer}</p>
                      {turn.evidence && <EvidenceDisclosure evidence={turn.evidence} id={`sticky-qa-evidence-${i}`} />}
                    </div>
                  )}
                </li>
              ))}
            </ul>

            <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-[var(--color-border)] px-3 py-2.5">
              <label htmlFor="sticky-qa-question" className="sr-only">
                Ask a question about this company
              </label>
              <input
                id="sticky-qa-question"
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask a question…"
                disabled={busy}
                className="input-field flex-1 px-3 py-2 text-sm"
              />
              <button
                type="submit"
                disabled={busy || !question.trim()}
                aria-label="Send question"
                className="btn-primary flex h-9 w-9 shrink-0 items-center justify-center rounded-full p-0 text-base"
              >
                ↑
              </button>
            </form>
          </>
        ) : (
          <p className="px-4 py-6 text-center text-xs text-[var(--color-text-faint)]">
            Once you search a ticker, ask grounded questions about its research here.
          </p>
        )}
      </div>

      <button
        id="ask-assistant-heading"
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? 'Collapse Ask Stock Agent' : 'Open Ask Stock Agent'}
        className={
          'pointer-events-auto flex items-center gap-2 rounded-full border border-[var(--color-accent)]/30 bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-strong)] px-4 py-3 text-sm font-semibold text-white shadow-[0_8px_24px_rgba(0,0,0,0.22)] transition-transform hover:scale-[1.03] active:scale-[0.98] ' +
          (open ? 'scale-95' : '')
        }
      >
        <span aria-hidden>✦</span>
        {open ? 'Ask Stock Agent' : 'Ask Stock Agent'}
      </button>
    </div>
  )
}
