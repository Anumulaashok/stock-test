import { useState } from 'react'
import { fetchLatestResearch } from '../../api/research'
import { formatCurrency } from '../../lib/format'
import { calculatePositionSize } from './positionSize'

/**
 * Arithmetic over user input and a real quote -- explicitly permitted
 * (I3). Output is always SCENARIO-badged (I11); the real, un-adjustable
 * current price stays visible alongside it as the actual anchor point.
 * No buy/sell/execute affordance anywhere here (I3) -- this computes a
 * share count, it does not place or prepare an order.
 */
export function PositionSizeCalculator() {
  const [ticker, setTicker] = useState('')
  const [formattedCurrentPrice, setFormattedCurrentPrice] = useState<string | null>(null)
  const [quoteError, setQuoteError] = useState<string | null>(null)
  const [loadingQuote, setLoadingQuote] = useState(false)

  const [accountSize, setAccountSize] = useState('')
  const [riskPercent, setRiskPercent] = useState('1')
  const [entryPrice, setEntryPrice] = useState('')
  const [stopPrice, setStopPrice] = useState('')

  async function handleLookup() {
    const trimmed = ticker.trim().toUpperCase()
    if (!trimmed) return
    setLoadingQuote(true)
    setQuoteError(null)
    try {
      const result = await fetchLatestResearch(trimmed)
      const market = result?.result.report?.market
      const price = market?.current_price ?? null
      if (price === null) {
        setFormattedCurrentPrice(null)
        setQuoteError('No live price available for this ticker.')
        return
      }
      setFormattedCurrentPrice(market?.formatted_current_price ?? price)
      setEntryPrice(price)
    } catch {
      setFormattedCurrentPrice(null)
      setQuoteError('Could not look up this ticker.')
    } finally {
      setLoadingQuote(false)
    }
  }

  const result = calculatePositionSize({
    accountSize: Number(accountSize), riskPercent: Number(riskPercent), entryPrice: Number(entryPrice), stopPrice: Number(stopPrice),
  })

  return (
    <div className="surface-card flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="card-heading">Position size calculator</h3>
        <span className="rounded-full border border-[var(--color-accent)] bg-[var(--color-accent-soft)] px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[var(--color-accent-strong)]">
          Scenario
        </span>
      </div>
      <p className="support-text text-xs">
        Computes a share count from what you enter below -- not a trade ticket, and not a recommendation to take this
        position.
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs sm:w-32">
          <span className="metric-label">Ticker to size</span>
          <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} placeholder="e.g. RELIANCE" className="input-field w-full px-3 py-1.5 font-mono-nums text-sm" />
        </label>
        <button type="button" onClick={() => void handleLookup()} disabled={loadingQuote || !ticker.trim()} className="btn-secondary px-3 py-1.5 text-xs">
          {loadingQuote ? 'Looking up…' : 'Look up price'}
        </button>
        {formattedCurrentPrice !== null && (
          <span className="text-xs text-[var(--color-text-faint)]">Current price: {formattedCurrentPrice}</span>
        )}
      </div>
      {quoteError && <p role="alert" className="text-xs text-[var(--color-status-negative)]">{quoteError}</p>}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <label className="flex flex-col gap-1 text-xs">
          <span className="metric-label">Account size</span>
          <input value={accountSize} onChange={(e) => setAccountSize(e.target.value)} inputMode="decimal" placeholder="e.g. 500000" className="input-field w-full px-3 py-1.5 font-mono-nums text-sm" />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="metric-label">Risk % of account</span>
          <input value={riskPercent} onChange={(e) => setRiskPercent(e.target.value)} inputMode="decimal" className="input-field w-full px-3 py-1.5 font-mono-nums text-sm" />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="metric-label">Entry price</span>
          <input value={entryPrice} onChange={(e) => setEntryPrice(e.target.value)} inputMode="decimal" placeholder="e.g. 2500" className="input-field w-full px-3 py-1.5 font-mono-nums text-sm" />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="metric-label">Stop price</span>
          <input value={stopPrice} onChange={(e) => setStopPrice(e.target.value)} inputMode="decimal" placeholder="e.g. 2400" className="input-field w-full px-3 py-1.5 font-mono-nums text-sm" />
        </label>
      </div>

      {result ? (
        <div className="grid grid-cols-3 gap-3 rounded-md border border-[var(--color-accent)]/40 bg-[var(--color-accent-soft)]/40 p-3">
          <div>
            <div className="metric-label">Shares</div>
            <div className="font-mono-nums text-lg font-semibold">{result.shareCount}</div>
          </div>
          <div>
            <div className="metric-label">Position value</div>
            <div className="font-mono-nums text-lg font-semibold">{formatCurrency(String(result.positionValue)) ?? result.positionValue}</div>
          </div>
          <div>
            <div className="metric-label">Amount at risk</div>
            <div className="font-mono-nums text-lg font-semibold">{formatCurrency(String(result.riskAmount)) ?? result.riskAmount}</div>
          </div>
        </div>
      ) : (
        <p className="support-text text-xs">Enter an account size, risk %, entry price, and stop price (different from entry) to compute a share count.</p>
      )}
    </div>
  )
}
