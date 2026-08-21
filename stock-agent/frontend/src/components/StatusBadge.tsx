import type { MetricStatus, Severity } from '../types/backend'

/**
 * The single place status/severity vocabulary is rendered. Every badge
 * pairs a color with text (never color alone), so status is legible
 * without relying on color perception.
 */

const METRIC_STATUS_LABEL: Record<MetricStatus, string> = {
  calculated: 'Calculated',
  unavailable: 'Unavailable',
  invalid: 'Invalid',
}

const METRIC_STATUS_CLASS: Record<MetricStatus, string> = {
  calculated: 'text-[var(--color-status-positive)] bg-[var(--color-status-positive)]/10',
  unavailable: 'text-[var(--color-text-faint)] bg-[var(--color-border)]',
  invalid: 'text-[var(--color-status-negative)] bg-[var(--color-status-negative)]/10',
}

export function MetricStatusBadge({ status }: { status: MetricStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${METRIC_STATUS_CLASS[status]}`}
    >
      {METRIC_STATUS_LABEL[status]}
    </span>
  )
}

const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

const SEVERITY_CLASS: Record<Severity, string> = {
  critical: 'text-[var(--color-status-critical)] bg-[var(--color-status-critical)]/10 border-[var(--color-status-critical)]/30',
  high: 'text-[var(--color-status-high)] bg-[var(--color-status-high)]/10 border-[var(--color-status-high)]/30',
  medium: 'text-[var(--color-status-medium)] bg-[var(--color-status-medium)]/10 border-[var(--color-status-medium)]/30',
  low: 'text-[var(--color-status-low)] bg-[var(--color-status-low)]/10 border-[var(--color-status-low)]/30',
}

export function SeverityBadge({ severity }: { severity: Severity | null }) {
  if (severity === null) {
    return (
      <span className="inline-flex items-center rounded border border-[var(--color-border)] px-1.5 py-0.5 text-xs font-medium text-[var(--color-text-faint)]">
        Informational
      </span>
    )
  }
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-semibold ${SEVERITY_CLASS[severity]}`}
    >
      {SEVERITY_LABEL[severity]}
    </span>
  )
}

const FRESHNESS_LABEL: Record<string, string> = {
  recent: 'Recent',
  stale: 'Stale',
  unknown: 'Unknown date',
}

export function FreshnessBadge({ freshness }: { freshness: string }) {
  const cls =
    freshness === 'recent'
      ? 'text-[var(--color-status-positive)] bg-[var(--color-status-positive)]/10'
      : freshness === 'stale'
        ? 'text-[var(--color-status-high)] bg-[var(--color-status-high)]/10'
        : 'text-[var(--color-text-faint)] bg-[var(--color-border)]'
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>
      {FRESHNESS_LABEL[freshness] ?? freshness}
    </span>
  )
}
