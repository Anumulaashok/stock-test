import { useStockReport } from '../../stock/StockReportContext'
import { TechnicalSection } from '../../components/stock/TechnicalSection'

export function TechnicalTab() {
  const { report } = useStockReport()
  return <TechnicalSection forecast={report.forecast} market={report.market} />
}
