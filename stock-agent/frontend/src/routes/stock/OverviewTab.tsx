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

/**
 * "Should I care about this stock?" -- verdict first, evidence after.
 * The hero score/signal, the plain-language thesis, the quick
 * positive/watch read, and risk (already self-collapsing per indicator
 * in `RiskOverview`) stay directly visible: together they answer the
 * question. The per-category score breakdown and the full AI analyst
 * writeup are real evidence but the longest, most granular content on
 * the tab, so both sit behind `Disclosure` instead of forcing a scroll
 * past them to reach anything else. Warnings stay last and keep its own
 * internal collapse behavior.
 */
export function OverviewTab() {
  const { report } = useStockReport()

  return (
    <>
      <InvestmentVerdict summary={report.summary} />
      <InvestorSummary report={report} />
      <WhyThisScore report={report} />
      <RiskOverview risk={report.risk} />
      <Disclosure summary="Score breakdown by category">
        <ScoreBreakdown scoring={report.scoring} hideHeading />
      </Disclosure>
      <Disclosure summary="AI Analyst Commentary">
        <AnalystSection analyst={report.analyst} evidenceValues={buildEvidenceValueMap(report)} />
      </Disclosure>
      <WarningsSection warnings={report.warnings} />
    </>
  )
}
