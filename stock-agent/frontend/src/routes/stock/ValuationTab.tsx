import { useStockReport } from '../../stock/StockReportContext'
import { ValuationSection } from '../../components/ValuationSection'

export function ValuationTab() {
  const { report } = useStockReport()
  return <ValuationSection valuation={report.valuation} />
}
