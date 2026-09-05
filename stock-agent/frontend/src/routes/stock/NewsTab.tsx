import { useStockReport } from '../../stock/StockReportContext'
import { ResearchSection } from '../../components/ResearchSection'

export function NewsTab() {
  const { report } = useStockReport()
  return <ResearchSection research={report.research} />
}
