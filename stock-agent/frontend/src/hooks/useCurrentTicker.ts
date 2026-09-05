import { useMatch } from 'react-router-dom'

/** The ticker of whatever `/stock/:ticker/*` route is currently active,
 * or `null` off that subtree -- lets `AppShell` mount a single
 * ticker-aware `StickyAskAssistant` instead of every page wiring its own
 * ask-ticker state. Uses `useMatch` (matched independently against the
 * current URL) rather than `useParams`, because `AppShell` renders
 * *above* the `/stock/:ticker` route in the tree and `useParams` only
 * sees params already matched at the calling component's own depth. */
export function useCurrentTicker(): string | null {
  const match = useMatch('/stock/:ticker/*')
  return match?.params.ticker ?? null
}
