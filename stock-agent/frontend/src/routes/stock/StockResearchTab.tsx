import { useSearchParams } from 'react-router-dom'
import { useStockReport } from '../../stock/StockReportContext'
import { ResearchHistorySection } from '../../components/ResearchHistorySection'

export function StockResearchTab() {
  const { ticker } = useStockReport()
  const [, setSearchParams] = useSearchParams()

  return (
    <ResearchHistorySection
      ticker={ticker}
      onSelectRun={(researchRunId) => setSearchParams({ run: researchRunId })}
    />
  )
}
