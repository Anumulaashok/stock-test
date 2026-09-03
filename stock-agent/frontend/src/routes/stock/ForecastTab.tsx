import { useStockReport } from '../../stock/StockReportContext'
import { ForecastSection } from '../../components/ForecastSection'

export function ForecastTab() {
  const { report } = useStockReport()
  return <ForecastSection forecast={report.forecast} />
}
