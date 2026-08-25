/**
 * TypeScript mirrors of the stock-agent backend's Pydantic models.
 *
 * Derived directly from `CombinedAnalysisResult.model_json_schema()` and
 * `InvestmentResearchReport.model_json_schema()` (Steps 6 & 9) — not
 * guessed. Field names, optionality, and enum values match the backend
 * exactly so nothing here silently drops a status the backend reports.
 *
 * IMPORTANT: the backend serializes Python `Decimal` fields as JSON
 * *strings* (e.g. `"value": "24.00"`), not numbers — every numeric field
 * below is typed `string`, and callers must go through `src/lib/format.ts`
 * rather than assuming a JS number.
 */

// --- Shared status/enum vocabulary (identical across backend layers) --------------

export type MetricStatus = 'calculated' | 'unavailable' | 'invalid'
export type ScoreBand = 'excellent' | 'strong' | 'good' | 'fair' | 'weak' | 'poor'
export type Severity = 'low' | 'medium' | 'high' | 'critical'
export type ResearchFreshness = 'recent' | 'stale' | 'unknown'
export type SourceType = 'news' | 'company' | 'regulatory' | 'market' | 'other'
export type PipelineStatus = 'calculated' | 'partial' | 'failed'
export type ReportStatus = PipelineStatus
export type ResultStatus = 'success' | 'error'

export interface AnalystEvidence {
  financial: string[]
  valuation: string[]
  risk: string[]
  research: string[]
}

// --- Report sections (Step 9) — the primary shape the UI renders ------------------

export interface ReportCompany {
  name: string
  ticker: string | null
  currency: string | null
}

export interface ReportMetadata {
  report_version: string
  generated_at: string
  pipeline_version: string | null
  duration_ms: number | null
}

export interface ReportWarning {
  source: string
  code: string | null
  message: string
}

export type SignalLabel = 'strong' | 'moderate' | 'weak' | 'unavailable'
export type SignalColor = 'green' | 'yellow' | 'red' | 'gray'

/** A deterministic strength/risk indicator derived from the score band
 * and risk indicators -- not investment advice, never a buy/sell/hold
 * recommendation (see app/reporting/signal.py). */
export interface ReportSignal {
  label: SignalLabel
  color: SignalColor
  reason: string
}

export interface ReportSummary {
  overall_score: string | null
  overall_status: string
  score_band: ScoreBand | null
  signal: ReportSignal | null
  investment_thesis: string | null
  key_takeaways: string[]
}

export interface ReportFinancialMetric {
  name: string
  value: string | null
  unit: string | null
  status: MetricStatus
  reason: string | null
  source_periods: string[]
  formatted_value: string | null
}

export interface ReportFinancialSection {
  source: string
  periods_analyzed: string[]
  profitability: ReportFinancialMetric[]
  growth: ReportFinancialMetric[]
  financial_health: ReportFinancialMetric[]
  cash_flow: ReportFinancialMetric[]
  other: ReportFinancialMetric[]
}

export interface ReportValuationMethod {
  method: string
  value_per_share: string | null
  status: MetricStatus
  reason: string | null
  upside_downside_percent: string | null
  upside_downside_status: MetricStatus | null
  assumptions: Record<string, string>
  formatted_value_per_share: string | null
  formatted_upside_downside: string | null
}

export interface ReportValuationSection {
  source: string
  current_share_price: string | null
  formatted_current_share_price: string | null
  methods: ReportValuationMethod[]
}

export interface ReportScoreComponent {
  name: string
  score: string | null
  weight: string
  status: MetricStatus
  reason: string | null
}

export interface ReportCategoryScore {
  category: string
  score: string | null
  weight: string
  status: MetricStatus
  band: ScoreBand | null
  reason: string | null
  components: ReportScoreComponent[]
}

export interface ReportScoringSection {
  source: string
  overall_score: string | null
  overall_status: string
  band: ScoreBand | null
  categories: ReportCategoryScore[]
}

export interface ReportRiskIndicator {
  name: string
  severity: Severity | null
  status: MetricStatus
  value: string | null
  threshold: string | null
  reason: string
}

export interface ReportRiskSection {
  source: string
  critical: ReportRiskIndicator[]
  high: ReportRiskIndicator[]
  medium: ReportRiskIndicator[]
  low: ReportRiskIndicator[]
  informational: ReportRiskIndicator[]
}

export interface ReportResearchItem {
  id: string
  title: string
  publisher: string | null
  published_at: string | null
  freshness: ResearchFreshness
  relevance: string | null
  summary: string | null
  url: string
  source_type: SourceType
}

export interface ReportResearchSection {
  source: string
  available: boolean
  items: ReportResearchItem[]
}

export interface ReportAnalystCategoryAnalysis {
  category: string
  text: string
  evidence: AnalystEvidence
}

export interface ReportAnalystSection {
  source: string
  available: boolean
  investment_thesis: string | null
  investment_thesis_evidence: AnalystEvidence | null
  strengths: string[]
  weaknesses: string[]
  category_analysis: ReportAnalystCategoryAnalysis[]
  key_takeaways: string[]
  caveats: string[]
}

export interface ReportEvidence {
  financial: string[]
  valuation: string[]
  risk: string[]
  research: string[]
}

// --- Forecast (deterministic extrapolation, never a recommendation) ---------------

export interface ReportForecastYear {
  year_offset: number
  value: string | null
  status: MetricStatus
  formatted_value: string | null
}

export interface ReportForecastMetric {
  name: string
  unit: string | null
  base_period: string | null
  base_value: string | null
  historical_cagr_percent: string | null
  status: MetricStatus
  reason: string | null
  formatted_historical_cagr: string | null
  projections: ReportForecastYear[]
}

export interface ReportValuationScenario {
  scenario: string
  fcf_growth_rate: string | null
  value_per_share: string | null
  status: MetricStatus
  reason: string | null
  formatted_value_per_share: string | null
}

export interface ReportPriceTrendPoint {
  day_offset: number
  projected_price: string | null
  formatted_projected_price: string | null
}

export interface ReportForecastSection {
  source: string
  available: boolean
  projection_years: number | null
  financial_metrics: ReportForecastMetric[]
  valuation_scenarios: ReportValuationScenario[]
  price_trend: ReportPriceTrendPoint[]
  price_trend_status: MetricStatus | null
  price_trend_reason: string | null
  price_trend_disclaimer: string | null
}

export interface InvestmentResearchReport {
  company: ReportCompany
  status: ReportStatus
  summary: ReportSummary
  financials: ReportFinancialSection | null
  valuation: ReportValuationSection | null
  scoring: ReportScoringSection | null
  risk: ReportRiskSection | null
  forecast: ReportForecastSection | null
  research: ReportResearchSection | null
  analyst: ReportAnalystSection | null
  evidence: ReportEvidence
  warnings: ReportWarning[]
  metadata: ReportMetadata
}

// --- CombinedAnalysisResult (Step 6) — the raw API response envelope --------------
// The UI renders `report` (above); these raw sections are kept typed for
// completeness/fallback but are not the primary rendering path.

export interface PipelineCompanyInfo {
  name: string
  ticker: string | null
}

export interface ExecutionMetadata {
  pipeline_version: string
  started_at: string
  completed_at: string
  duration_ms: number
}

export interface AnalystError {
  code: string
  message: string
}

export interface AnalystResponse {
  company_name: string
  investment_thesis: { text: string; evidence: AnalystEvidence }
  strengths: string[]
  weaknesses: string[]
  profitability_analysis: { text: string; evidence: AnalystEvidence }
  growth_analysis: { text: string; evidence: AnalystEvidence }
  financial_health_analysis: { text: string; evidence: AnalystEvidence }
  cash_flow_analysis: { text: string; evidence: AnalystEvidence }
  valuation_analysis: { text: string; evidence: AnalystEvidence }
  risk_analysis: { text: string; evidence: AnalystEvidence }
  key_takeaways: string[]
  caveats: string[]
}

export interface AnalystResult {
  status: ResultStatus
  response: AnalystResponse | null
  error: AnalystError | null
}

export interface CombinedAnalysisResult {
  company: PipelineCompanyInfo
  status: PipelineStatus
  financial_analysis: unknown | null
  valuation: unknown | null
  scoring: unknown | null
  research: unknown | null
  analyst: AnalystResult | null
  report: InvestmentResearchReport | null
  warnings: string[]
  metadata: ExecutionMetadata | null
}

// --- Request contract ---------------------------------------------------------------

export interface TickerAnalysisRequest {
  ticker: string
  include_report: true
  include_price_trend_forecast?: boolean
}

// --- Auth / portfolio (Step 11) -----------------------------------------------------
// Mirrors app/models/user.py and app/models/portfolio.py. As elsewhere in this
// file, Decimal fields are serialized as JSON strings, not numbers.

export interface UserPublic {
  id: string
  email: string
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserPublic
}

export interface Holding {
  id: string
  ticker: string
  quantity: string
  average_cost: string
  added_at: string
  updated_at: string
}

export type PriceStatus = 'live' | 'delayed' | 'stale' | 'unavailable'

export interface HoldingWithMarketData extends Holding {
  current_price: string | null
  price_status: PriceStatus
  market_value: string | null
  unrealized_gain: string | null
  unrealized_gain_percent: string | null
}

export interface PortfolioSummary {
  portfolio_id: string
  invested_capital: string
  portfolio_value: string | null
  unrealized_gain: string | null
  unrealized_gain_percent: string | null
  holdings: HoldingWithMarketData[]
  warnings: string[]
}

export interface WatchlistItem {
  ticker: string
  created_at: string
}
