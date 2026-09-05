import { useState } from 'react'
import { fetchForecastAccuracy } from '../../api/marketHistory'
import { InvestmentScorePerformanceSection, ModelPerformancePanel } from '../../features/settings/ModelPerformancePanel'
import { TickerPicker } from '../../features/settings/TickerPicker'
import { AsyncSection } from '../../components/ui/AsyncSection'
import { useAsync } from '../../hooks/useAsync'

/** Per-ticker forecast-accuracy backtest -- there is no cross-ticker
 * accuracy endpoint, so this is a ticker picker over
 * `fetchForecastAccuracy`. Score-bucket performance has no backend
 * support yet and renders as a static, honest "unavailable" section. */
export function ModelPerformanceSettingsPage() {
  const [ticker, setTicker] = useState<string | null>(null)

  const state = useAsync(
    () => fetchForecastAccuracy(ticker as string),
    [ticker],
    { enabled: ticker !== null },
  )

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-base font-semibold">Model Performance</h2>
        <p className="support-text">
          Per-ticker forecast backtest results. There is no cross-ticker accuracy endpoint -- pick a ticker to see how
          its saved forecasts compared against what actually happened.
        </p>
      </div>

      <TickerPicker onSubmit={setTicker} placeholder="e.g. RELIANCE" label="Ticker symbol" />

      {ticker === null ? (
        <p className="support-text">Enter a ticker to view its forecast accuracy.</p>
      ) : (
        <AsyncSection state={state} onRetry={state.reload} errorTitle="Could not load forecast accuracy">
          {(summary) => <ModelPerformancePanel summary={summary} />}
        </AsyncSection>
      )}

      <InvestmentScorePerformanceSection />
    </div>
  )
}
