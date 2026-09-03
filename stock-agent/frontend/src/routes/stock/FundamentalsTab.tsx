import { useStockReport } from '../../stock/StockReportContext'
import { FinancialSection } from '../../components/FinancialSection'
import { DataQualitySection } from '../../components/DataQualitySection'
import { WarningsSection } from '../../components/WarningsSection'

/** `DataQualitySection` points readers to "Data Quality & Warnings below"
 * -- that reference dangled here until `WarningsSection` was added; it
 * already renders on Overview and Risk, so Fundamentals was the one tab
 * making a promise it didn't keep. */
export function FundamentalsTab() {
  const { report } = useStockReport()
  return (
    <>
      <FinancialSection financials={report.financials} />
      <DataQualitySection report={report} />
      <WarningsSection warnings={report.warnings} />
    </>
  )
}
