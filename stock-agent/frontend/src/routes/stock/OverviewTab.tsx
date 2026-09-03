import { useStockReport } from '../../stock/StockReportContext'
import { InvestmentVerdict } from '../../components/stock/InvestmentVerdict'
import { ScoreBreakdown } from '../../components/stock/ScoreBreakdown'
import { WhyThisScore } from '../../components/stock/WhyThisScore'
import { InvestorSummary } from '../../components/stock/InvestorSummary'
import { RiskOverview } from '../../components/stock/RiskOverview'
import { AnalystSection } from '../../components/AnalystSection'
import { WarningsSection } from '../../components/WarningsSection'
import { Disclosure } from '../../components/ui/Disclosure'
import { buildEvidenceValueMap } from '../../lib/evidenceValues'

/** "Should I care about this stock?" -- placeholder composition of the
 * existing decision-first components (see `d70b0a6`). Owned by Phase 2
 * Agent A, which will refine this into the final Overview tab. */
export function OverviewTab() {
  const { report } = useStockReport()

  return (
    <>
      <InvestmentVerdict summary={report.summary} />
      <ScoreBreakdown scoring={report.scoring} />
      <WhyThisScore report={report} />
      <InvestorSummary report={report} />
      <RiskOverview risk={report.risk} />
      <Disclosure summary="AI Analyst Commentary" defaultOpen>
        <AnalystSection analyst={report.analyst} evidenceValues={buildEvidenceValueMap(report)} />
      </Disclosure>
      <WarningsSection warnings={report.warnings} />
    </>
  )
}
