import { useState } from 'react'
import { fetchLatestResearch } from '../../api/research'
import { DataQualitySection } from '../../components/DataQualitySection'
import { AsyncSection } from '../../components/ui/AsyncSection'
import { TickerPicker } from '../../features/settings/TickerPicker'
import { useAsync } from '../../hooks/useAsync'

/** Per-ticker data quality -- there is no global/cross-ticker
 * data-quality endpoint, so this is a ticker picker over the same
 * `DataQualitySection` the stock research tab already renders, never a
 * synthesized cross-portfolio score. */
export function DataQualitySettingsPage() {
  const [ticker, setTicker] = useState<string | null>(null)

  const state = useAsync(
    () => fetchLatestResearch(ticker as string),
    [ticker],
    { enabled: ticker !== null },
  )

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-base font-semibold">Data Quality</h2>
        <p className="support-text">
          Per-ticker report completeness. There is no global data-quality score across all tickers -- pick a ticker
          to see how much of its latest research report was calculated versus unavailable.
        </p>
      </div>

      <TickerPicker onSubmit={setTicker} placeholder="e.g. RELIANCE" label="Ticker symbol" />

      {ticker === null ? (
        <p className="support-text">Enter a ticker to view its data quality.</p>
      ) : (
        <AsyncSection state={state} onRetry={state.reload} errorTitle="Could not load data quality">
          {(result) =>
            result?.result.report ? (
              <DataQualitySection report={result.result.report} />
            ) : (
              <p className="support-text">
                No research has been run for {ticker} yet, so there is no data-quality report to show.
              </p>
            )
          }
        </AsyncSection>
      )}
    </div>
  )
}
