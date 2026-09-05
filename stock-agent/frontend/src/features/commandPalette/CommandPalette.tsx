import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { parseCommand } from './parseCommand'

export const OPEN_COMMAND_PALETTE_EVENT = 'open-command-palette'

/**
 * Global ⌘K/Ctrl+K palette -- parses a typed command into an existing
 * route (`parseCommand`) rather than opening any new page of its own.
 * Mounted once in `AppShell` so the shortcut works from any route.
 */
export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  function openPalette() {
    setValue('')
    setError(null)
    setOpen(true)
  }

  useEffect(() => {
    function handleGlobalKeyDown(event: globalThis.KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        if (open) {
          setOpen(false)
        } else {
          openPalette()
        }
      }
    }
    window.addEventListener('keydown', handleGlobalKeyDown)
    window.addEventListener(OPEN_COMMAND_PALETTE_EVENT, openPalette)
    return () => {
      window.removeEventListener('keydown', handleGlobalKeyDown)
      window.removeEventListener(OPEN_COMMAND_PALETTE_EVENT, openPalette)
    }
  }, [open])

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus())
  }, [open])

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setOpen(false)
      return
    }
    if (event.key !== 'Enter') return
    const result = parseCommand(value)
    if (result === null) return
    if ('error' in result) {
      setError(result.error)
      return
    }
    setOpen(false)
    navigate(result.path)
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[15vh]"
      onClick={() => setOpen(false)}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onClick={(e) => e.stopPropagation()}
        className="surface-card w-full max-w-lg overflow-hidden shadow-[var(--shadow-lg)]"
      >
        <input
          ref={inputRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            setError(null)
          }}
          onKeyDown={handleKeyDown}
          placeholder='Try "RELIANCE", "compare TCS INFY", "screen score>70", or "watchlist"'
          autoComplete="off"
          spellCheck={false}
          className="w-full bg-transparent px-4 py-3 font-mono-nums text-sm text-[var(--color-text)] outline-none"
        />
        {error && (
          <p role="alert" className="border-t border-[var(--color-border)] px-4 py-2 text-xs text-[var(--color-status-negative)]">
            {error}
          </p>
        )}
        <div className="border-t border-[var(--color-border)] px-4 py-2 text-xs text-[var(--color-text-faint)]">
          Enter to go · Esc to close
        </div>
      </div>
    </div>
  )
}
