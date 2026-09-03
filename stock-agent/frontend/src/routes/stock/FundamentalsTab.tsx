import { useStockReport } from '../../stock/StockReportContext'
import { FinancialSection } from '../../components/FinancialSection'
import { DataQualitySection } from '../../components/DataQualitySection'

export function FundamentalsTab() {
  const { report } = useStockReport()
  return (
    <>
      <FinancialSection financials={report.financials} />
      <DataQualitySection report={report} />
    </>
  )
}
