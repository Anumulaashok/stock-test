import { useStockReport } from '../../stock/StockReportContext'
import { ForecastSection } from '../../components/ForecastSection'
import { MlForecastPanel } from '../../components/stock/MlForecastPanel'
import { MlAccuracyPanel } from '../../components/stock/MlAccuracyPanel'

export function ForecastTab() {
  const { ticker, report } = useStockReport()
  return (
    <div className="flex flex-col gap-8">
      <MlForecastPanel ticker={ticker} historicalPrices={report.forecast?.historical_prices ?? []} />
      <MlAccuracyPanel ticker={ticker} />
      <div>
        <h3 className="mb-2 text-base font-semibold">Technical Baseline</h3>
        <ForecastSection forecast={report.forecast} market={report.market} />
      </div>
    </div>
  )
}
