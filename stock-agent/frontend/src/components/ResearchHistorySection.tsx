import { useEffect, useState } from 'react'
import { fetchResearchHistory, fetchResearchRun } from '../api/research'
import { ApiError } from '../api/client'
import { SectionHeader } from './SectionHeader'
import { formatDateTime } from '../lib/format'
import { ResearchRunDiffView } from '../features/research/ResearchRunDiffView'
import type { InvestmentResearchReport, ResearchRunStatusKey, ResearchRunSummary } from '../types/backend'

type CompareState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; oldLabel: string; newLabel: string; oldReport: InvestmentResearchReport; newReport: InvestmentResearchReport }

const RUN_TYPE_LABEL: Record<string, string> = {
  NORMAL: 'Normal',
  FORCE_REFRESH: 'Force Refresh',
}

const STATUS_CLASS: Record<ResearchRunStatusKey, string> = {
  COMPLETED: 'text-[var(--color-status-positive)] bg-[var(--color-status-positive)]/10',
  PARTIAL: 'text-[var(--color-status-high)] bg-[var(--color-status-high)]/10',
  FAILED: 'text-[var(--color-status-negative)] bg-[var(--color-status-negative)]/10',
  RUNNING: 'text-[var(--color-text-faint)] bg-[var(--color-border)]',
  PENDING: 'text-[var(--color-text-faint)] bg-[var(--color-border)]',
}

/**
 * A lightweight, collapsed-by-default list of past research runs for
 * the ticker on screen. Selecting a row loads that EXACT saved report
 * (`onSelectRun`) -- it must never trigger a new analysis.
 */
export function ResearchHistorySection({
  ticker,
  onSelectRun,
}: {
  ticker: string
  onSelectRun: (researchRunId: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<ResearchRunSummary[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([])
  const [compareState, setCompareState] = useState<CompareState>({ status: 'idle' })

  // A new ticker (or a fresh/forced run that changes history) means the
  // previously-loaded list is stale -- refetch the next time it's opened.
  useEffect(() => {
    setItems(null)
    setError(null)
    setOpen(false)
    setSelectedForCompare([])
    setCompareState({ status: 'idle' })
  }, [ticker])

  function toggleCompareSelection(runId: string) {
    setCompareState({ status: 'idle' })
    setSelectedForCompare((prev) => {
      if (prev.includes(runId)) return prev.filter((id) => id !== runId)
      if (prev.length >= 2) return [prev[1], runId]
      return [...prev, runId]
    })
  }

  async function handleCompare() {
    if (selectedForCompare.length !== 2 || !items) return
    setCompareState({ status: 'loading' })
    try {
      const [firstId, secondId] = selectedForCompare
      const firstItem = items.find((i) => i.id === firstId)!
      const secondItem = items.find((i) => i.id === secondId)!
      // Older run first, regardless of click order.
      const [olderId, olderItem, newerId, newerItem] =
        firstItem.research_date <= secondItem.research_date
          ? [firstId, firstItem, secondId, secondItem]
          : [secondId, secondItem, firstId, firstItem]
      const [oldRun, newRun] = await Promise.all([fetchResearchRun(ticker, olderId), fetchResearchRun(ticker, newerId)])
      if (!oldRun.result.report || !newRun.result.report) {
        setCompareState({ status: 'error', message: 'One of these runs has no saved report to compare.' })
        return
      }
      setCompareState({
        status: 'ready',
        oldLabel: formatDateTime(olderItem.completed_at ?? olderItem.started_at) ?? olderItem.research_date,
        newLabel: formatDateTime(newerItem.completed_at ?? newerItem.started_at) ?? newerItem.research_date,
        oldReport: oldRun.result.report,
        newReport: newRun.result.report,
      })
    } catch (err) {
      setCompareState({ status: 'error', message: err instanceof ApiError ? err.message : 'Could not load these runs.' })
    }
  }

  async function handleToggle() {
    const next = !open
    setOpen(next)
    if (!next || items !== null) return
    setLoading(true)
    setError(null)
    try {
      setItems(await fetchResearchHistory(ticker))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load research history.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section aria-labelledby="research-history-heading">
      <SectionHeader
        id="research-history-heading"
        title="Research History"
        action={
          <button
            type="button"
            onClick={handleToggle}
            className="text-sm font-medium text-[var(--color-text-muted)] underline-offset-2 hover:underline"
          >
            {open ? 'Hide' : 'Show'}
          </button>
        }
      />
      {open && (
        <div className="surface-card overflow-x-auto">
          {loading && <p className="p-3 text-sm text-[var(--color-text-faint)]">Loading…</p>}
          {error && <p className="p-3 text-sm text-[var(--color-status-negative)]">{error}</p>}
          {items && items.length === 0 && (
            <p className="p-3 text-sm text-[var(--color-text-faint)]">No past research for {ticker} yet.</p>
          )}
          {items && items.length > 0 && (
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-text-faint)]">
                  <th className="px-3 py-2 font-medium" title="Select exactly two runs to compare">Compare</th>
                  <th className="px-3 py-2 font-medium">Ticker</th>
                  <th className="px-3 py-2 font-medium">Research Date</th>
                  <th className="px-3 py-2 font-medium">Time</th>
                  <th className="px-3 py-2 font-medium">Run Type</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium text-right">&nbsp;</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {items.map((item) => {
                  const timestamp = item.completed_at ?? item.started_at
                  const formatted = formatDateTime(timestamp)
                  const [datePart, timePart] = formatted ? formatted.split(' · ') : [item.research_date, null]
                  return (
                    <tr key={item.id} className="transition-colors hover:bg-[var(--color-border)]/30">
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={selectedForCompare.includes(item.id)}
                          onChange={() => toggleCompareSelection(item.id)}
                          aria-label={`Select ${item.research_date} run for comparison`}
                          className="h-3.5 w-3.5 rounded border-[var(--color-border-strong)] accent-[var(--color-accent)]"
                        />
                      </td>
                      <td className="px-3 py-2 font-mono-nums font-semibold">{item.ticker}</td>
                      <td className="px-3 py-2 font-mono-nums text-[var(--color-text-muted)]">{datePart}</td>
                      <td className="px-3 py-2 font-mono-nums text-[var(--color-text-muted)]">{timePart ?? '—'}</td>
                      <td className="px-3 py-2 text-[var(--color-text-faint)]">{RUN_TYPE_LABEL[item.run_type] ?? item.run_type}</td>
                      <td className="px-3 py-2">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_CLASS[item.status]}`}>
                          {item.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => onSelectRun(item.id)}
                          className="inline-flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] px-2.5 py-1 text-xs font-medium text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
          {items && items.length > 1 && (
            <div className="flex items-center gap-2 border-t border-[var(--color-border)] px-3 py-2">
              <button
                type="button"
                onClick={handleCompare}
                disabled={selectedForCompare.length !== 2 || compareState.status === 'loading'}
                className="rounded-[var(--radius-sm)] border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {compareState.status === 'loading' ? 'Loading…' : 'Compare selected'}
              </button>
              <span className="text-xs text-[var(--color-text-faint)]">
                {selectedForCompare.length}/2 selected
              </span>
            </div>
          )}
        </div>
      )}

      {compareState.status === 'error' && (
        <p role="alert" className="mt-2 text-sm text-[var(--color-status-negative)]">
          {compareState.message}
        </p>
      )}
      {compareState.status === 'ready' && (
        <div className="mt-3">
          <ResearchRunDiffView
            oldLabel={compareState.oldLabel}
            newLabel={compareState.newLabel}
            oldReport={compareState.oldReport}
            newReport={compareState.newReport}
          />
        </div>
      )}
    </section>
  )
}
