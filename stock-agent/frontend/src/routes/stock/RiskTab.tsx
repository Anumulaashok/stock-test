import { useStockReport } from '../../stock/StockReportContext'
import { RiskOverview } from '../../components/stock/RiskOverview'
import { WarningsSection } from '../../components/WarningsSection'

export function RiskTab() {
  const { report } = useStockReport()
  return (
    <>
      <RiskOverview risk={report.risk} />
      <WarningsSection warnings={report.warnings} />
    </>
  )
}
