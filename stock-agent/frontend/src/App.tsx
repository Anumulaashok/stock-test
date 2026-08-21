import { AnalysisPage } from './pages/AnalysisPage'

export default function App() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <span className="font-mono-nums text-sm font-semibold tracking-wide">STOCK-AGENT</span>
          <span className="text-xs text-[var(--color-text-faint)]">Research terminal</span>
        </div>
      </header>
      <AnalysisPage />
    </div>
  )
}
