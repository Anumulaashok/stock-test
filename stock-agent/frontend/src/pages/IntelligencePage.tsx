import { useEffect, useRef, useState } from 'react'
import { fetchMarketOpportunity } from '../api/sectors'
import { askTickerQuestion } from '../api/qa'
import { fetchLatestResearch } from '../api/research'
import { fetchWatchlist } from '../api/portfolio'
import {
  clearScreenerCookie,
  fetchIndexQuotes,
  fetchScreenerCookieStatus,
  importHistoricalPrices,
  registerScreenerCompanyMappings,
  searchCompanies,
  setScreenerCookie,
} from '../api/marketHistory'
import { ApiError } from '../api/client'
import { toDisplayNumber, formatDate } from '../lib/format'
import { SearchBar } from '../components/SearchBar'
import { StickyAskAssistant } from '../components/StickyAskAssistant'
import DataSourcesPanel from '../components/DataSourcesPanel'
import { useAuth } from '../auth/AuthContext'
import type {
  CompanySearchResponse,
  CompanySearchResult,
  IndexQuote,
  MarketOpportunityResult,
  ResearchRunResult,
  ScreenerCookieStatus,
  SectorSummary,
  SectorStockSummary,
} from '../types/backend'

interface IntelligencePageProps {
  onAnalyze: (ticker: string) => void
  onGoToDashboard: () => void
  onExit: () => void
}

// --- icons ---------------------------------------------------------------------------
// Minimal line icons, matching the weight/style of the existing LockIcon
// in App.tsx -- no icon library dependency for a handful of glyphs.

function Icon({ path, className = 'h-4 w-4' }: { path: string; className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className={className}>
      <path d={path} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const ICON = {
  core: 'M4 12 L12 4 L20 12 M6 10 V19 H18 V10',
  overview: 'M4 19 V10 M10 19 V5 M16 19 V13 M22 19 H2',
  pulse: 'M3 12 H8 L10 6 L14 18 L16 12 H21',
  sectors: 'M12 3 L20 7.5 V16.5 L12 21 L4 16.5 V7.5 Z M12 3 V21 M4 7.5 L12 12 L20 7.5',
  screener: 'M4 5 H20 M7 5 L7 12 L12 19 L12 12 M17 5 L17 12',
  watchlist: 'M12 4 L14.5 9.5 L20.5 10.3 L16 14.3 L17.2 20.2 L12 17.2 L6.8 20.2 L8 14.3 L3.5 10.3 L9.5 9.5 Z',
  archive: 'M3 7 H21 V21 H3 Z M3 7 L5 3 H19 L21 7 M10 12 H14',
  lock: 'M6 10.5 H18 V19.5 H6 Z M8.5 10.5 V7 A3.5 3.5 0 0 1 15.5 7 V10.5',
  search: 'M11 4 A7 7 0 1 0 11 18 A7 7 0 1 0 11 4 Z M20 20 L16 16',
  bell: 'M6 9 A6 6 0 0 1 18 9 C18 14 20 15 20 15 H4 C4 15 6 14 6 9 Z M10 18 A2 2 0 0 0 14 18',
  send: 'M4 12 L20 4 L14 20 L11 13 L4 12 Z',
}

// --- small shared bits ----------------------------------------------------------------

function LockedBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-text-faint)]">
      <Icon path={ICON.lock} className="h-2.5 w-2.5" />
      Locked
    </span>
  )
}

function score(value: string | null): string {
  return toDisplayNumber(value, 0) ?? '—'
}

const OUTLOOK_DOT: Record<SectorSummary['outlook'], string> = {
  bullish: 'bg-[var(--color-status-positive)]',
  neutral: 'bg-[var(--color-status-info)]',
  bearish: 'bg-[var(--color-status-negative)]',
}

// --- sidebar ---------------------------------------------------------------------------

const NAV_ITEMS: { label: string; icon: string; active?: boolean }[] = [
  { label: 'Intelligence Core', icon: ICON.core, active: true },
  { label: 'Market Overview', icon: ICON.overview },
  { label: 'Asset Pulse', icon: ICON.pulse },
  { label: 'Quantum Sectors', icon: ICON.sectors },
  { label: 'Strategic Screener', icon: ICON.screener },
  { label: 'Predictive Watchlist', icon: ICON.watchlist },
  { label: 'Archive & Research', icon: ICON.archive },
]

function Sidebar({
  onGoToDashboard,
  onExit,
  onGoToResearch,
}: {
  onGoToDashboard: () => void
  onExit: () => void
  onGoToResearch: () => void
}) {
  return (
    <aside className="hidden w-60 shrink-0 flex-col gap-6 border-r border-[var(--color-border)] px-4 py-6 lg:flex">
      <button type="button" onClick={onExit} className="flex items-center gap-2 px-1 text-left" title="Back to Research">
        <span
          aria-hidden="true"
          className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-gradient-to-br from-[var(--intel-violet)] to-[var(--intel-teal)] text-sm font-bold text-white shadow-[var(--shadow-sm)]"
        >
          S
        </span>
        <div className="leading-tight">
          <div className="text-[13px] font-bold tracking-wide">Stock Agent</div>
          <div className="text-[10px] text-[var(--color-text-faint)]">Research · Sectors · Platforms</div>
        </div>
      </button>

      <nav className="flex flex-col gap-0.5">
        {NAV_ITEMS.map((item) => {
          const isDashboardLink = item.label === 'Market Overview'
          const isArchiveLink = item.label === 'Archive & Research'
          const isBuilt = item.active || isDashboardLink || isArchiveLink
          const onClick = isDashboardLink ? onGoToDashboard : isArchiveLink ? onGoToResearch : undefined
          return (
            <button
              key={item.label}
              type="button"
              disabled={!isBuilt}
              onClick={onClick}
              title={isBuilt ? undefined : 'Coming soon'}
              className={`flex items-center gap-2.5 rounded-[var(--radius-md)] px-3 py-2 text-left text-[13px] font-medium transition-colors ${
                item.active
                  ? 'bg-[var(--color-accent-soft)] text-[var(--color-text)]'
                  : isBuilt
                    ? 'text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]'
                    : 'cursor-not-allowed text-[var(--color-text-faint)]/60'
              }`}
            >
              <Icon path={item.icon} className="h-4 w-4 shrink-0" />
              <span className="flex-1">{item.label}</span>
              {!isBuilt && <Icon path={ICON.lock} className="h-3 w-3 shrink-0" />}
            </button>
          )
        })}
      </nav>

      <div className="mt-auto rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-center">
        <div
          aria-hidden="true"
          className="mx-auto mb-3 h-14 w-14 rounded-full bg-gradient-to-br from-[var(--intel-violet)] to-[var(--intel-teal)] opacity-80 blur-[2px]"
        />
        <p className="text-[11px] italic leading-relaxed text-[var(--color-text-faint)]">
          "Discipline builds wealth, not predictions."
        </p>
      </div>
    </aside>
  )
}

// --- top bar ---------------------------------------------------------------------------

function TopBar({ onAnalyze }: { onAnalyze: (ticker: string) => void }) {
  const { user } = useAuth()
  const today = new Date()
  const dateLabel = today.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })

  return (
    <header className="flex flex-wrap items-center gap-3 border-b border-[var(--color-border)] px-5 py-3.5 sm:gap-4">
      <div className="min-w-0 flex-1">
        <SearchBar onSubmit={onAnalyze} disabled={false} />
      </div>
      <div className="flex items-center gap-3 text-right">
        <div className="hidden text-xs sm:block">
          <div className="font-medium text-[var(--color-text)]">{dateLabel}</div>
          <div className="text-[var(--color-text-faint)]">Live research session</div>
        </div>
        <span className="hidden h-8 w-px bg-[var(--color-border)] sm:block" aria-hidden="true" />
        <button
          type="button"
          title="Notifications (coming soon)"
          disabled
          className="flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-border)] text-[var(--color-text-faint)]"
        >
          <Icon path={ICON.bell} className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-accent-soft)] text-xs font-semibold text-[var(--color-accent-strong)]">
            {(user?.email ?? '?').slice(0, 2).toUpperCase()}
          </span>
          <span className="hidden text-xs font-medium text-[var(--color-text-muted)] md:inline">{user?.email}</span>
        </div>
      </div>
    </header>
  )
}

// --- hero ---------------------------------------------------------------------------

function Hero() {
  return (
    <div className="surface-card relative overflow-hidden p-6 sm:p-8">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-[color-mix(in_srgb,var(--intel-violet)_28%,transparent)] blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-20 right-24 h-56 w-56 rounded-full bg-[color-mix(in_srgb,var(--intel-teal)_22%,transparent)] blur-3xl"
      />
      <p className="section-heading relative">Deterministic Market Intelligence</p>
      <h1 className="relative mt-2 max-w-xl text-2xl font-bold leading-tight sm:text-3xl">
        Every score on this page traces back to a real, computed number
      </h1>
      <p className="relative mt-2 max-w-lg text-sm text-[var(--color-text-muted)]">
        Sector rankings and stock scores below come straight from this app's own deterministic scoring engine — no
        LLM-invented numbers, and no metric shown without a real source behind it.
      </p>
    </div>
  )
}

// --- global pulse (locked -- no aggregate market-vibe metric exists yet) --------------

function GlobalPulseLocked() {
  return (
    <div className="surface-card flex flex-col items-center gap-3 p-5 text-center">
      <div className="flex w-full items-center justify-between">
        <h2 className="card-heading">Global Pulse Monitor</h2>
        <LockedBadge />
      </div>
      <div className="relative flex h-32 w-32 items-center justify-center">
        <svg viewBox="0 0 120 120" className="h-32 w-32 -rotate-90 opacity-30">
          <circle cx="60" cy="60" r="52" fill="none" stroke="var(--color-border-strong)" strokeWidth="10" strokeDasharray="245 327" strokeLinecap="round" />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
          <Icon path={ICON.lock} className="h-5 w-5 text-[var(--color-text-faint)]" />
        </div>
      </div>
      <p className="support-text">
        An aggregated market-mood score isn't computed by this app yet — no fabricated number is shown in its place.
      </p>
    </div>
  )
}

// --- index ticker strip: Nifty 50 / Sensex via the real yfinance-backed
// /api/v1/market/indices endpoint. USD/INR and Gold still have no wired
// provider, so they stay honestly locked rather than showing a fabricated dash. ----

const LOCKED_TICKERS = ['USD/INR', 'Gold'] as const

function formatIndexChange(quote: IndexQuote): { text: string; tone: 'positive' | 'negative' | 'neutral' } {
  if (quote.change_percent === null) return { text: '—', tone: 'neutral' }
  const value = Number(quote.change_percent)
  if (Number.isNaN(value)) return { text: '—', tone: 'neutral' }
  const sign = value > 0 ? '+' : ''
  return { text: `${sign}${value.toFixed(2)}%`, tone: value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral' }
}

function IndexTickerCard({ quote }: { quote: IndexQuote }) {
  if (quote.status !== 'available' || quote.current_price === null) {
    return (
      <div className="surface-card flex items-center justify-between gap-2 p-3">
        <div>
          <div className="text-xs font-semibold text-[var(--color-text-muted)]">{quote.name}</div>
          <div className="font-mono-nums text-sm text-[var(--color-text-faint)]">— . —</div>
        </div>
        <span className="badge bg-[var(--color-status-medium)]/15 text-[var(--color-status-medium)]" title={quote.warning ?? undefined}>
          Unavailable
        </span>
      </div>
    )
  }
  const change = formatIndexChange(quote)
  const toneClass =
    change.tone === 'positive'
      ? 'text-[var(--color-status-positive)]'
      : change.tone === 'negative'
        ? 'text-[var(--color-status-negative)]'
        : 'text-[var(--color-text-faint)]'
  return (
    <div className="surface-card flex items-center justify-between gap-2 p-3">
      <div>
        <div className="text-xs font-semibold text-[var(--color-text-muted)]">{quote.name}</div>
        <div className="font-mono-nums text-sm">{Number(quote.current_price).toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
      </div>
      <div className="text-right">
        <span className={`font-mono-nums text-sm font-medium ${toneClass}`}>{change.text}</span>
        <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">{quote.freshness ?? quote.source}</div>
      </div>
    </div>
  )
}

function IndexTickerStrip() {
  const [indices, setIndices] = useState<IndexQuote[] | null>(null)

  useEffect(() => {
    fetchIndexQuotes()
      .then((response) => setIndices(response.indices))
      .catch(() => setIndices([]))
  }, [])

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {(indices ?? [{ name: 'Nifty 50' }, { name: 'Sensex' }]).map((quote, i) =>
        'status' in quote ? (
          <IndexTickerCard key={quote.symbol} quote={quote as IndexQuote} />
        ) : (
          <div key={i} className="surface-card flex items-center justify-between gap-2 p-3">
            <div>
              <div className="text-xs font-semibold text-[var(--color-text-muted)]">{quote.name}</div>
              <div className="font-mono-nums text-sm text-[var(--color-text-faint)]">Loading…</div>
            </div>
          </div>
        ),
      )}
      {LOCKED_TICKERS.map((name) => (
        <div key={name} className="surface-card flex items-center justify-between gap-2 p-3">
          <div>
            <div className="text-xs font-semibold text-[var(--color-text-muted)]">{name}</div>
            <div className="font-mono-nums text-sm text-[var(--color-text-faint)]">— . —</div>
          </div>
          <LockedBadge />
        </div>
      ))}
    </div>
  )
}

// --- market opportunity: real sector data ----------------------------------------------

function SectorMiniCard({
  sector,
  rank,
  selected,
  onSelect,
}: {
  sector: SectorSummary
  rank: number
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`surface-card surface-card--interactive flex min-w-[150px] flex-col gap-2 p-3.5 text-left ${
        selected ? 'border-[var(--color-accent)]' : ''
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--color-accent-soft)] text-[11px] font-bold text-[var(--color-accent-strong)]">
          {rank}
        </span>
        <span className={`h-2 w-2 rounded-full ${OUTLOOK_DOT[sector.outlook]}`} title={sector.outlook} />
      </div>
      <div className="text-[13px] font-semibold leading-tight">{sector.sector}</div>
      <div className="flex items-baseline gap-1">
        <span className="metric-value text-xl">{score(sector.sector_score)}</span>
        <span className="text-[10px] text-[var(--color-text-faint)]">/100</span>
      </div>
      <dl className="grid grid-cols-3 gap-x-1.5 gap-y-0.5 text-[10px] text-[var(--color-text-faint)]">
        <div className="min-w-0">
          <dt className="truncate">Growth</dt>
          <dd className="font-mono-nums text-[var(--color-text-muted)]">{score(sector.growth_score)}</dd>
        </div>
        <div className="min-w-0">
          <dt className="truncate" title="Valuation">Val.</dt>
          <dd className="font-mono-nums text-[var(--color-text-muted)]">{score(sector.valuation_score)}</dd>
        </div>
        <div className="min-w-0">
          <dt className="truncate" title="Momentum">Mtm.</dt>
          <dd className="font-mono-nums text-[var(--color-text-muted)]">{score(sector.momentum_score)}</dd>
        </div>
      </dl>
    </button>
  )
}

function BestStocksTable({ sector, onPick }: { sector: SectorSummary | null; onPick: (ticker: string) => void }) {
  const stocks: SectorStockSummary[] = sector?.top_stocks ?? []
  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="card-heading">Best Stocks {sector ? `· ${sector.sector}` : ''}</h2>
          <p className="support-text">Top performers from this sector's evaluated constituents.</p>
        </div>
        {sector && (
          <span className="badge bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]">
            Score {score(sector.sector_score)}
          </span>
        )}
      </div>

      {stocks.length === 0 && <p className="support-text">No sector selected yet.</p>}

      {stocks.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-[var(--color-text-faint)]">
              <tr>
                <th className="pb-2 pr-2">#</th>
                <th className="pb-2 pr-2">Stock</th>
                <th className="pb-2 pr-2">Score</th>
                <th className="pb-2 pr-2">
                  <span className="inline-flex items-center gap-1">
                    Price <Icon path={ICON.lock} className="h-2.5 w-2.5" />
                  </span>
                </th>
                <th className="pb-2 pr-2">
                  <span className="inline-flex items-center gap-1">
                    1W Trend <Icon path={ICON.lock} className="h-2.5 w-2.5" />
                  </span>
                </th>
                <th className="pb-2">
                  <span className="inline-flex items-center gap-1">
                    Upside <Icon path={ICON.lock} className="h-2.5 w-2.5" />
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {stocks.map((stock, i) => (
                <tr key={stock.ticker} className="border-t border-[var(--color-border)]">
                  <td className="py-2 pr-2 text-[var(--color-text-faint)]">{i + 1}</td>
                  <td className="py-2 pr-2">
                    <button
                      type="button"
                      onClick={() => onPick(stock.ticker)}
                      className="font-medium text-[var(--color-accent-strong)] hover:underline"
                    >
                      {stock.ticker}
                    </button>
                    <div className="text-[11px] text-[var(--color-text-faint)]">{stock.company_name}</div>
                  </td>
                  <td className="py-2 pr-2 font-mono-nums">
                    {stock.status === 'calculated' ? score(stock.overall_score) : '—'}
                  </td>
                  <td className="py-2 pr-2 font-mono-nums text-[var(--color-text-faint)]">—</td>
                  <td className="py-2 pr-2 font-mono-nums text-[var(--color-text-faint)]">—</td>
                  <td className="py-2 font-mono-nums text-[var(--color-text-faint)]">—</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function MarketOpportunitySection({ onSelectTicker }: { onSelectTicker: (ticker: string) => void }) {
  const [data, setData] = useState<MarketOpportunityResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedSector, setSelectedSector] = useState<string | null>(null)

  useEffect(() => {
    fetchMarketOpportunity(false)
      .then((result) => {
        setData(result)
        if (result.sectors.length > 0) setSelectedSector(result.sectors[0].sector)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load sector rankings.'))
      .finally(() => setLoading(false))
  }, [])

  const selected = data?.sectors.find((s) => s.sector === selectedSector) ?? data?.sectors[0] ?? null

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h2 className="section-heading">Market Opportunity</h2>
        <p className="support-text">Sectors ranked by average deterministic score across curated constituents.</p>
      </div>

      {loading && <p className="support-text">Loading sector rankings…</p>}
      {error && <p className="text-sm text-[var(--color-status-critical)]">{error}</p>}
      {data && data.status === 'unavailable' && (
        <p className="support-text">Sector ranking is unavailable — configure a financial data provider to enable it.</p>
      )}

      {data && data.sectors.length > 0 && (
        <>
          <div className="flex gap-3 overflow-x-auto pb-1">
            {data.sectors.map((sector, i) => (
              <SectorMiniCard
                key={sector.sector}
                sector={sector}
                rank={i + 1}
                selected={sector.sector === selected?.sector}
                onSelect={() => setSelectedSector(sector.sector)}
              />
            ))}
          </div>

          <BestStocksTable sector={selected} onPick={onSelectTicker} />
        </>
      )}
    </section>
  )
}

// --- ask stock agent ---------------------------------------------------------------------

const QUICK_QUERIES = ['Is this overvalued?', 'What is the FCF trend?', 'Key risks right now?', 'How does it score?']

function AskStockAgentPanel({ ticker }: { ticker: string | null }) {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<string | null>(null)
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function ask(text: string) {
    if (!ticker || !text.trim()) return
    setAsking(true)
    setError(null)
    setAnswer(null)
    try {
      const result = await askTickerQuestion(ticker, text)
      if (result.status === 'success' && result.response) {
        setAnswer(result.response.answer)
      } else {
        setError(result.error?.message ?? 'The assistant could not answer that.')
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the assistant.')
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="surface-card flex h-full flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <h2 className="card-heading">Ask Stock Agent</h2>
        {ticker && <span className="badge bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]">{ticker}</span>}
      </div>

      {!ticker && <p className="support-text">Pick a stock from Best Stocks above to ask about it.</p>}

      {ticker && (
        <>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_QUERIES.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => {
                  setQuestion(q)
                  ask(q)
                }}
                disabled={asking}
                className="btn-secondary px-2.5 py-1 text-[11px]"
              >
                {q}
              </button>
            ))}
          </div>

          <div className="min-h-[80px] flex-1 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-3 text-sm">
            {asking && <p className="support-text">Thinking…</p>}
            {!asking && error && <p className="text-[var(--color-status-critical)]">{error}</p>}
            {!asking && answer && <p className="leading-relaxed text-[var(--color-text)]">{answer}</p>}
            {!asking && !answer && !error && (
              <p className="support-text">Ask a quick-query chip above, or type your own question below.</p>
            )}
          </div>

          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              ask(question)
            }}
          >
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about a stock or sector here…"
              className="input-field min-w-0 flex-1 px-3 py-2 text-sm"
            />
            <button type="submit" disabled={asking || !question.trim()} className="btn-primary h-9 w-9 shrink-0 p-0">
              <Icon path={ICON.send} className="h-4 w-4" />
            </button>
          </form>
        </>
      )}
    </div>
  )
}

// --- recent research (Archive & Research) -----------------------------------------------
// Real, already-computed data: the latest saved research snapshot for
// each watchlist ticker (app/api/research.py's read-only routes --
// never triggers a new computation just by viewing this list).

const STATUS_DOT: Record<string, string> = {
  COMPLETED: 'bg-[var(--color-status-positive)]',
  PARTIAL: 'bg-[var(--color-status-medium)]',
  FAILED: 'bg-[var(--color-status-negative)]',
  RUNNING: 'bg-[var(--color-status-info)]',
  PENDING: 'bg-[var(--color-status-info)]',
}

function RecentResearchCard({ result, onOpen }: { result: ResearchRunResult; onOpen: () => void }) {
  const overallScore = result.result.report?.scoring?.overall_score ?? null
  return (
    <button
      type="button"
      onClick={onOpen}
      className="surface-card surface-card--interactive flex min-w-[190px] flex-col gap-2 p-3.5 text-left"
    >
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-semibold">{result.ticker}</span>
        <span
          className={`flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-[var(--color-text-faint)]`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[result.status] ?? 'bg-[var(--color-text-faint)]'}`} />
          {result.status.toLowerCase()}
        </span>
      </div>
      <div className="truncate text-[11px] text-[var(--color-text-faint)]">{result.result.company.name}</div>
      <div className="flex items-baseline gap-1">
        <span className="metric-value text-lg">{overallScore ? score(overallScore) : '—'}</span>
        <span className="text-[10px] text-[var(--color-text-faint)]">/100</span>
      </div>
      <div className="text-[10px] text-[var(--color-text-faint)]">
        {formatDate(result.research_date) ?? result.research_date}
      </div>
    </button>
  )
}

function RecentResearchSection({ onOpenTicker }: { onOpenTicker: (ticker: string) => void }) {
  const [results, setResults] = useState<ResearchRunResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const watchlist = await fetchWatchlist()
        const fetched = await Promise.all(
          watchlist.map((item) => fetchLatestResearch(item.ticker).catch(() => null)),
        )
        if (!cancelled) setResults(fetched.filter((r): r is ResearchRunResult => r !== null))
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Could not load recent research.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section id="recent-research-heading" className="flex flex-col gap-4">
      <div>
        <h2 className="section-heading">Archive &amp; Research</h2>
        <p className="support-text">
          The latest saved research snapshot for every ticker on your watchlist — never recomputed just by viewing
          this list.
        </p>
      </div>

      {loading && <p className="support-text">Loading recent research…</p>}
      {error && <p className="text-sm text-[var(--color-status-critical)]">{error}</p>}
      {!loading && !error && results.length === 0 && (
        <p className="support-text">
          Nothing researched yet — add a ticker to your Watchlist and analyze it once, and it'll show up here.
        </p>
      )}

      {results.length > 0 && (
        <div className="flex gap-3 overflow-x-auto pb-1">
          {results.map((result) => (
            <RecentResearchCard key={result.ticker} result={result} onOpen={() => onOpenTicker(result.ticker)} />
          ))}
        </div>
      )}
    </section>
  )
}

// --- historical data import (Screener.in bulk backfill) ------------------------------
// A one-time, manually-triggered backfill -- Screener has no public
// ticker-search API, so its numeric company id must be supplied by
// hand (see app/data/screener_import_service.py). Feeds
// daily_price_history, which the ongoing daily accumulation and
// forecast-accuracy evaluation both build on.

function TickerMappingAutocomplete({
  value,
  onChange,
  onPick,
}: {
  value: string
  onChange: (value: string) => void
  onPick: (result: CompanySearchResult) => void
}) {
  const [suggestions, setSuggestions] = useState<CompanySearchResult[]>([])
  const [source, setSource] = useState<CompanySearchResponse['source'] | null>(null)
  const [open, setOpen] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestIdRef = useRef(0)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const query = value.trim()
    if (query.length < 1) {
      setSuggestions([])
      setOpen(false)
      return
    }
    const thisRequestId = ++requestIdRef.current
    debounceRef.current = setTimeout(() => {
      searchCompanies(query)
        .then((response) => {
          if (thisRequestId !== requestIdRef.current) return
          setSuggestions(response.results)
          setSource(response.source)
          setOpen(response.results.length > 0)
        })
        .catch(() => {
          if (thisRequestId !== requestIdRef.current) return
          setSuggestions([])
          setOpen(false)
        })
    }, 250)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [value])

  return (
    <div className="relative">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase())}
        onFocus={() => suggestions.length > 0 && setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        placeholder="Ticker or company name, e.g. HDFCBANK"
        className="input-field w-full px-3 py-2 text-sm"
      />
      {open && (
        <ul className="absolute z-10 mt-1 w-max min-w-full max-w-[360px] overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] shadow-[var(--shadow-md)]">
          {suggestions.map((s) => (
            <li key={s.ticker}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onPick(s)
                  setOpen(false)
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-[var(--color-accent-soft)]"
              >
                <span className="min-w-0 flex-1 truncate">
                  <span className="font-medium">{s.ticker}</span>
                  {s.company_name && <span className="ml-2 truncate text-[var(--color-text-faint)]">{s.company_name}</span>}
                </span>
                <span className="shrink-0 font-mono-nums text-xs text-[var(--color-text-faint)]">
                  {s.screener_company_id !== null ? `#${s.screener_company_id}` : '—'}
                </span>
              </button>
            </li>
          ))}
          <li className="border-t border-[var(--color-border)] px-3 py-1.5 text-[10px] uppercase tracking-wide text-[var(--color-text-faint)]">
            Source: {source === 'screener' ? 'Screener.in (live)' : 'Local NSE directory'}
          </li>
        </ul>
      )}
    </div>
  )
}

function HistoricalImportWidget() {
  const [ticker, setTicker] = useState('')
  const [companyId, setCompanyId] = useState('')
  const [days, setDays] = useState('365')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)

  async function handleImport() {
    if (!ticker.trim()) return
    setStatus('loading')
    setMessage(null)
    try {
      const result = await importHistoricalPrices(ticker, {
        screener_company_id: companyId.trim() ? Number(companyId) : null,
        days: Number(days) || 365,
        consolidated: true,
      })
      setStatus('success')
      setMessage(
        `Imported ${result.rows_imported} day${result.rows_imported === 1 ? '' : 's'}` +
          (result.earliest_date && result.latest_date ? ` (${result.earliest_date} → ${result.latest_date}).` : '.'),
      )
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof ApiError ? err.message : 'Import failed.')
    }
  }

  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <div>
        <h2 className="card-heading">Import Historical Data</h2>
        <p className="support-text">
          One-time backfill from Screener.in. Start typing a ticker — if it's already mapped (via a prior import or
          the bulk list-import below), pick it and the Screener id fills in automatically; otherwise enter the id
          manually once and it's remembered from then on.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_100px_auto]">
        <TickerMappingAutocomplete
          value={ticker}
          onChange={setTicker}
          onPick={(result) => {
            setTicker(result.ticker)
            setCompanyId(result.screener_company_id !== null ? String(result.screener_company_id) : '')
          }}
        />
        <input
          value={companyId}
          onChange={(e) => setCompanyId(e.target.value)}
          type="number"
          min="1"
          placeholder="Screener company id (optional if mapped)"
          className="input-field px-3 py-2 text-sm"
        />
        <input
          value={days}
          onChange={(e) => setDays(e.target.value)}
          type="number"
          min="1"
          placeholder="Days"
          className="input-field px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={handleImport}
          disabled={status === 'loading' || !ticker.trim()}
          className="btn-primary px-4 py-2 text-sm"
        >
          {status === 'loading' ? 'Importing…' : 'Import'}
        </button>
      </div>
      {message && (
        <p className={`text-xs ${status === 'error' ? 'text-[var(--color-status-critical)]' : 'text-[var(--color-status-positive)]'}`}>
          {message}
        </p>
      )}
    </div>
  )
}

// --- bulk ticker->screener-id mapping import (paste Screener's own
// company-search JSON, reused going forward for autocomplete + auto-lookup) ------------

function MappingListImportWidget() {
  const [raw, setRaw] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)

  async function handleImport() {
    let parsed: unknown
    try {
      parsed = JSON.parse(raw)
    } catch {
      setStatus('error')
      setMessage('That is not valid JSON — paste the array exactly as Screener returned it.')
      return
    }
    if (!Array.isArray(parsed)) {
      setStatus('error')
      setMessage('Expected a JSON array of {id, name, url} objects.')
      return
    }
    setStatus('loading')
    setMessage(null)
    try {
      const result = await registerScreenerCompanyMappings(parsed)
      setStatus('success')
      setMessage(
        `Registered ${result.registered} ticker${result.registered === 1 ? '' : 's'}` +
          (result.skipped > 0 ? ` (${result.skipped} skipped — no id or unparseable url).` : '.'),
      )
      setRaw('')
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof ApiError ? err.message : 'Import failed.')
    }
  }

  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <div>
        <h2 className="card-heading">Bulk-Register Screener IDs</h2>
        <p className="support-text">
          Paste a Screener company-search JSON result (a list of <code className="font-mono-nums">{'{id, name, url}'}</code>{' '}
          objects) to register every ticker → Screener-id mapping at once — reused automatically by the ticker
          autocomplete above and by future imports, so you never look the id up twice.
        </p>
      </div>
      <textarea
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        placeholder='[{"id": 681, "name": "Coal India Ltd", "url": "/company/COALINDIA/consolidated/"}, ...]'
        rows={4}
        className="input-field w-full px-3 py-2 font-mono-nums text-xs"
      />
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleImport}
          disabled={status === 'loading' || !raw.trim()}
          className="btn-primary px-4 py-2 text-sm"
        >
          {status === 'loading' ? 'Registering…' : 'Register list'}
        </button>
        {message && (
          <p className={`text-xs ${status === 'error' ? 'text-[var(--color-status-critical)]' : 'text-[var(--color-status-positive)]'}`}>
            {message}
          </p>
        )}
      </div>
    </div>
  )
}

// --- Screener session cookie settings -------------------------------------------------
// Runtime-editable (no server restart) -- takes effect immediately for
// live company search and gets used by future imports.

/**
 * Distinguishes "a cookie is stored" from "the stored cookie works" --
 * previously any stored cookie showed as Active, including an expired one.
 */
function ScreenerCookieBadge({ status }: { status: ScreenerCookieStatus }) {
  if (!status.configured) {
    return (
      <span className="badge shrink-0 bg-[var(--color-status-medium)]/15 text-[var(--color-status-medium)]">
        Not configured
      </span>
    )
  }

  const bad = status.status === 'AUTH_EXPIRED' || status.status === 'INVALID'
  const warn = status.status === 'UNREACHABLE' || status.status === 'RATE_LIMITED'
  const label =
    status.status === 'SUCCESS'
      ? `Valid (${status.source})`
      : status.status === 'AUTH_EXPIRED'
        ? 'Expired — re-authenticate'
        : status.status === 'INVALID'
          ? 'Invalid response'
          : status.status === 'UNREACHABLE'
            ? 'Screener unreachable'
            : status.status === 'RATE_LIMITED'
              ? 'Rate limited'
              : `Stored (${status.source}) — not checked`

  const tone = bad
    ? 'bg-[var(--color-status-critical)]/15 text-[var(--color-status-critical)]'
    : warn
      ? 'bg-[var(--color-status-medium)]/15 text-[var(--color-status-medium)]'
      : status.status === 'SUCCESS'
        ? 'bg-[var(--color-status-positive)]/15 text-[var(--color-status-positive)]'
        : 'bg-[var(--color-status-info)]/15 text-[var(--color-status-info)]'

  return (
    <span className={`badge shrink-0 ${tone}`} title={status.detail ?? undefined}>
      {label}
    </span>
  )
}

function ScreenerCookieSettingsWidget() {
  const [status, setStatus] = useState<ScreenerCookieStatus | null>(null)
  const [cookieInput, setCookieInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  function load() {
    fetchScreenerCookieStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
  }

  useEffect(() => {
    load()
  }, [])

  async function handleSave() {
    if (!cookieInput.trim()) return
    setSaving(true)
    setMessage(null)
    try {
      const result = await setScreenerCookie(cookieInput.trim())
      setStatus(result)
      setCookieInput('')
      setMessage('Cookie saved — live Screener search is active immediately, no restart needed.')
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : 'Could not save the cookie.')
    } finally {
      setSaving(false)
    }
  }

  async function handleClear() {
    setSaving(true)
    setMessage(null)
    try {
      const result = await clearScreenerCookie()
      setStatus(result)
      setMessage(
        result.configured
          ? 'Runtime cookie cleared — falling back to the server-configured one.'
          : 'Cookie cleared — company search now uses the local NSE directory.',
      )
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : 'Could not clear the cookie.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="card-heading">Screener.in Session</h2>
          <p className="support-text">
            Paste your Screener <code className="font-mono-nums">sessionid</code> cookie value to enable live company
            search (used to resolve tickers to Screener ids). Without it, company search falls back to the local NSE
            directory — Screener imports and Nifty 50 / Sensex both keep working either way.
          </p>
        </div>
        {status && <ScreenerCookieBadge status={status} />}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={cookieInput}
          onChange={(e) => setCookieInput(e.target.value)}
          type="password"
          placeholder="Paste sessionid cookie value…"
          className="input-field min-w-0 flex-1 px-3 py-2 font-mono-nums text-xs"
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !cookieInput.trim()}
            className="btn-primary px-4 py-2 text-sm"
          >
            Save
          </button>
          {status?.source === 'runtime' && (
            <button type="button" onClick={handleClear} disabled={saving} className="btn-secondary px-4 py-2 text-sm">
              Clear
            </button>
          )}
        </div>
      </div>
      {message && <p className="text-xs text-[var(--color-text-faint)]">{message}</p>}
    </div>
  )
}

// --- page ---------------------------------------------------------------------------

export function IntelligencePage({ onAnalyze, onGoToDashboard, onExit }: IntelligencePageProps) {
  const [askTicker, setAskTicker] = useState<string | null>(null)

  function scrollToResearch() {
    document.getElementById('recent-research-heading')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="intel-theme flex min-h-screen">
      <Sidebar onGoToDashboard={onGoToDashboard} onExit={onExit} onGoToResearch={scrollToResearch} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onAnalyze={onAnalyze} />
        <main className="flex flex-1 flex-col gap-5 px-5 py-5">
          <DataSourcesPanel />

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_320px]">
            <Hero />
            <GlobalPulseLocked />
          </div>

          <IndexTickerStrip />

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_360px]">
            <MarketOpportunitySection onSelectTicker={(t) => setAskTicker(t)} />
            <AskStockAgentPanel ticker={askTicker} />
          </div>

          <RecentResearchSection onOpenTicker={onAnalyze} />

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <HistoricalImportWidget />
            <MappingListImportWidget />
          </div>

          <ScreenerCookieSettingsWidget />
        </main>
      </div>

      <StickyAskAssistant ticker={askTicker} />
    </div>
  )
}
