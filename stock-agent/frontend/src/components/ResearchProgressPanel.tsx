import { useEffect, useRef, useState } from 'react'
import { fetchResearchProgress } from '../api/research'
import type { ResearchProgress, ResearchStage, ResearchStageStatusKey } from '../types/backend'

const POLL_MS = 1200

const STATUS_ICON: Record<ResearchStageStatusKey, string> = {
  pending: '○',
  running: '◐',
  success: '✓',
  failed: '✕',
  skipped: '–',
}

const STATUS_CLASS: Record<ResearchStageStatusKey, string> = {
  pending: 'text-[var(--color-text-faint)]',
  running: 'text-[var(--color-accent)]',
  success: 'text-[var(--color-status-positive)]',
  failed: 'text-[var(--color-status-negative)]',
  skipped: 'text-[var(--color-text-faint)]',
}

function StageRow({ stage }: { stage: ResearchStage }) {
  return (
    <li className="flex items-start gap-2.5 py-1">
      <span
        aria-hidden="true"
        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center text-xs font-bold ${STATUS_CLASS[stage.status]} ${
          stage.status === 'running' ? 'animate-pulse' : ''
        }`}
      >
        {STATUS_ICON[stage.status]}
      </span>
      <div className="min-w-0">
        <span className={`text-sm ${stage.status === 'pending' || stage.status === 'skipped' ? 'text-[var(--color-text-faint)]' : 'text-[var(--color-text)]'}`}>
          {stage.label}
        </span>
        {stage.detail && stage.status === 'failed' && (
          <p className="mt-0.5 text-xs text-[var(--color-status-negative)]">{stage.detail}</p>
        )}
      </div>
    </li>
  )
}

/**
 * Polls `GET /api/v1/research/{ticker}/progress` while a `runNew()` call
 * is in flight (see `StockReportContext`'s `computing` flag) and renders
 * real stage-by-stage status -- never a fabricated/animated checklist
 * with no data behind it (see `LoadingState.tsx`'s docstring on why a
 * fake one was deliberately avoided before this endpoint existed). A
 * 404 (nothing known yet, e.g. the very first poll before the backend
 * has created its in-memory progress entry) falls back to a plain
 * "Starting…" line rather than an error.
 */
export function ResearchProgressPanel({ ticker }: { ticker: string }) {
  const [progress, setProgress] = useState<ResearchProgress | null>(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    cancelledRef.current = false
    setProgress(null)
    let timer: ReturnType<typeof setTimeout> | null = null

    async function poll() {
      try {
        const result = await fetchResearchProgress(ticker)
        if (cancelledRef.current) return
        setProgress(result)
        if (result?.finished) return // stop polling once the run has reached a terminal state
      } catch {
        // A transient poll failure never breaks the loading UI -- just
        // keep the last-known state and try again next tick.
      }
      if (!cancelledRef.current) timer = setTimeout(poll, POLL_MS)
    }

    void poll()
    return () => {
      cancelledRef.current = true
      if (timer) clearTimeout(timer)
    }
  }, [ticker])

  return (
    <div role="status" aria-live="polite" className="animate-fade-in-up flex flex-col items-center gap-4 py-16 text-center">
      <div className="relative flex h-14 w-14 items-center justify-center">
        <span aria-hidden="true" className="absolute inset-0 animate-ping rounded-full bg-[var(--color-accent)]/15" />
        <div
          className="h-10 w-10 animate-spin rounded-full border-[3px] border-[var(--color-border)] border-t-[var(--color-accent)]"
          aria-hidden="true"
        />
      </div>
      <p className="font-mono-nums text-lg font-semibold">Analyzing {ticker}…</p>

      {progress && progress.stages.length > 0 ? (
        <ul className="w-full max-w-sm text-left">
          {progress.stages.map((stage) => (
            <StageRow key={stage.key} stage={stage} />
          ))}
        </ul>
      ) : (
        <p className="max-w-sm text-sm text-[var(--color-text-faint)]">
          Starting research — this can take up to a minute or two.
        </p>
      )}
    </div>
  )
}
