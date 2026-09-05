import { Icon, ICON } from './ui/Icon'
import { useTheme } from '../theme/ThemeContext'

/** Explicit opt-in toggle (D8) -- dark is the designed-for default,
 * light is a deliberate switch, not a system-preference follow. */
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const nextTheme = theme === 'dark' ? 'light' : 'dark'

  return (
    <button
      type="button"
      onClick={toggleTheme}
      title={`Switch to ${nextTheme} theme`}
      className="flex shrink-0 items-center justify-center rounded-[var(--radius-sm)] border border-[var(--color-border)] p-2 text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
    >
      <Icon path={theme === 'dark' ? ICON.sun : ICON.moon} className="h-4 w-4" />
      <span className="sr-only">Switch to {nextTheme} theme</span>
    </button>
  )
}
