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
export type TechnicalSignalLabel = 'bullish' | 'bearish' | 'neutral' | 'mixed' | 'unavailable'

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

export type ForecastHorizonKey = 'daily' | 'weekly' | 'monthly'

export interface ReportPriceTrendPoint {
  period: number
  day_offset: number
  date: string | null
  projected_price: string | null
  formatted_projected_price: string | null
}

/** An actual (already-observed) daily OHLCV bar -- never a projection.
 * `open`/`high`/`low`/`volume` are populated by the backend
 * (app/models/report.py's ReportHistoricalPricePoint) but were missing
 * from this mirror; only `close` was previously exposed here. */
export interface ReportHistoricalPricePoint {
  date: string
  open?: string | null
  high?: string | null
  low?: string | null
  close: string | null
  volume?: string | null
  formatted_close: string | null
}

/** Current market quote fields -- fetched separately from the financial
 * statements and never merged into them (see app/market/). Populated
 * only when a market snapshot was available for this run. This mirrors
 * `ReportMarketSection` (app/models/report.py), which the backend has
 * always emitted at `report.market` but this file previously omitted. */
export interface ReportMarketSection {
  source: string
  current_price: string | null
  previous_close: string | null
  change: string | null
  change_percent: string | null
  currency: string | null
  market_status: string
  market_timestamp: string | null
  freshness: string
  market_cap: string | null
  year_high: string | null
  year_low: string | null
  formatted_current_price: string | null
}

export interface ReportMovingAverage {
  window: number
  value: string | null
  status: MetricStatus
  reason: string | null
  formatted_value: string | null
}

export interface ReportMovingAverageCrossover {
  short_window: number
  long_window: number
  signal: string | null
  status: MetricStatus
  reason: string | null
}

export interface ReportTechnicalMethod {
  method: string
  description: string
  projected_price: string | null
  projection_days: number
  horizon: ForecastHorizonKey
  horizon_period: number
  projected_date: string | null
  status: MetricStatus
  reason: string | null
  formatted_projected_price: string | null
}

export interface ReportTechnicalSignal {
  label: TechnicalSignalLabel
  color: SignalColor
  reason: string
}

/** One forecast horizon's (daily/weekly/monthly) price-trend line and
 * technical-method projections. `price_trend` is a genuine per-period
 * series; `technical_methods` stay single values at the horizon's
 * terminal period (see the backend's `HorizonForecast` docstring). */
export interface ReportHorizonForecast {
  horizon: ForecastHorizonKey
  label: string
  price_trend: ReportPriceTrendPoint[]
  price_trend_status: MetricStatus | null
  price_trend_reason: string | null
  moving_averages: ReportMovingAverage[]
  crossover: ReportMovingAverageCrossover | null
  technical_methods: ReportTechnicalMethod[]
  technical_signal: ReportTechnicalSignal | null
}

export interface ReportMultiHorizonForecast {
  daily: ReportHorizonForecast
  weekly: ReportHorizonForecast
  monthly: ReportHorizonForecast
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
  moving_averages: ReportMovingAverage[]
  crossover: ReportMovingAverageCrossover | null
  technical_methods: ReportTechnicalMethod[]
  technical_disclaimer: string | null
  technical_signal: ReportTechnicalSignal | null
  current_price: string | null
  formatted_current_price: string | null
  horizons: ReportMultiHorizonForecast | null
  historical_prices: ReportHistoricalPricePoint[]
}

export interface InvestmentResearchReport {
  company: ReportCompany
  status: ReportStatus
  summary: ReportSummary
  market: ReportMarketSection | null
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

// --- Research snapshots (POST /api/v1/research/ticker, GET .../history) -------------

export type ResearchRunStatusKey = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'PARTIAL'
export type ResearchRunTypeKey = 'NORMAL' | 'FORCE_REFRESH'

/** One row of research history -- enough to render a history list
 * without loading the full saved report. */
export interface ResearchRunSummary {
  id: string
  ticker: string
  research_date: string
  run_type: ResearchRunTypeKey
  status: ResearchRunStatusKey
  started_at: string
  completed_at: string | null
  error_message: string | null
}

/** What `POST /api/v1/research/ticker` and the read-only history routes
 * return -- the same `CombinedAnalysisResult` shape (`result`) the app
 * already renders, plus snapshot metadata for "Research snapshot ·
 * Sep 2, 2026" and whether this call did new work or replayed one. */
export interface ResearchRunResult {
  research_run_id: string
  ticker: string
  research_date: string
  run_type: ResearchRunTypeKey
  status: ResearchRunStatusKey
  is_new_run: boolean
  started_at: string
  completed_at: string | null
  result: CombinedAnalysisResult
}

// --- Request contract ---------------------------------------------------------------

export interface TickerAnalysisRequest {
  ticker: string
  include_report: true
  include_price_trend_forecast?: boolean
}

// --- AI Q&A assistant -----------------------------------------------------------------
// Mirrors app/models/qa.py. Deliberately has no buy/sell/hold or probability
// field -- see app/qa/prompts.py for why the assistant never produces one.

export interface QAResponse {
  answer: string
  evidence: AnalystEvidence
  recommendation_declined: boolean
}

export interface QAError {
  code: string
  message: string
}

export interface QAResult {
  status: ResultStatus
  response: QAResponse | null
  error: QAError | null
}

export interface QATickerRequest {
  ticker: string
  question: string
}

// --- Market Opportunity / sector ranking ---------------------------------------------
// Mirrors app/models/sectors.py. `sector_score` is the average of the sector's
// constituent tickers' ScoringResult.overall_score -- never LLM-computed.

export interface SectorStockSummary {
  ticker: string
  company_name: string
  overall_score: string | null
  band: string | null
  status: 'calculated' | 'unavailable'
}

export interface SectorSummary {
  sector: string
  sector_score: string | null
  outlook: 'bullish' | 'neutral' | 'bearish'
  risk: 'low' | 'medium' | 'high'
  growth_score: string | null
  valuation_score: string | null
  momentum_score: string | null
  news_headline_count: number
  constituents_evaluated: number
  constituents_total: number
  top_stocks: SectorStockSummary[]
}

export interface MarketOpportunityResult {
  status: 'success' | 'partial' | 'unavailable'
  generated_at: string
  sectors: SectorSummary[]
  warnings: string[]
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

// --- Historical price store / Screener import (app/api/market.py) -------------------

export interface ScreenerImportRequest {
  screener_company_id?: number | null
  days?: number
  consolidated?: boolean
}

export interface ScreenerImportResult {
  ticker: string
  rows_imported: number
  earliest_date: string | null
  latest_date: string | null
  /** Which provider actually supplied the rows -- not necessarily Screener. */
  source: string
  status: 'SUCCESS' | 'FALLBACK' | 'UNAVAILABLE'
  fallback_used: boolean
  detail: string | null
}

export interface ScreenerCompanyListImportResult {
  registered: number
  skipped: number
}

export interface ScreenerMappingSummary {
  ticker: string
  company_name: string | null
  screener_company_id: number
  consolidated: boolean
}

export type CompanySearchSource = 'screener' | 'local_directory'

export interface CompanySearchResult {
  ticker: string
  company_name: string | null
  screener_company_id: number | null
  source: CompanySearchSource
}

export interface CompanySearchResponse {
  query: string
  source: CompanySearchSource
  source_detail: string
  results: CompanySearchResult[]
}

export type ScreenerCookieSource = 'runtime' | 'env'

/**
 * NOT_CONFIGURED  no cookie stored at all
 * SUCCESS         validated against Screener
 * AUTH_EXPIRED    Screener rejected the cookie (401/403)
 * RATE_LIMITED    Screener throttled the check; cookie may still be valid
 * UNREACHABLE     Screener could not be reached; validation inconclusive
 * INVALID         unexpected response shape
 * UNKNOWN         stored but not validated yet
 */
export type SourceStatusValue =
  | 'NOT_CONFIGURED'
  | 'SUCCESS'
  | 'AUTH_EXPIRED'
  | 'RATE_LIMITED'
  | 'UNREACHABLE'
  | 'INVALID'
  | 'UNKNOWN'

export interface ScreenerCookieStatus {
  configured: boolean
  source: ScreenerCookieSource | null
  status: SourceStatusValue
  last_validated_at: string | null
  last_success_at: string | null
  last_error_at: string | null
  detail: string | null
}

/**
 * One data source's declared capabilities and observed health. Deliberately
 * separates being *configured* from being *capable* of a category from being
 * the *active* choice for it. See app/api/market.py.
 */
export interface DataSourceStatus {
  name: string
  label: string
  type: string
  configured: boolean
  status: SourceStatusValue | string
  capabilities: string[]
  primary_for: string[]
  fallback_for: string[]
  last_success_at: string | null
  last_error_at: string | null
  limitation: string | null
}

export interface DataSourceStatusResponse {
  sources: DataSourceStatus[]
}

export interface IndexQuote {
  name: string
  symbol: string
  status: 'available' | 'unavailable'
  current_price: string | null
  previous_close: string | null
  change: string | null
  change_percent: string | null
  source: string
  freshness: string | null
  warning: string | null
}

export interface IndexQuotesResponse {
  indices: IndexQuote[]
}

export interface ForecastAccuracyEntry {
  horizon: string
  method: string
  prediction_date: string
  target_date: string
  predicted_price: string | null
  actual_price: string | null
  absolute_error: string | null
  percentage_error: string | null
  direction_correct: boolean | null
}

export interface ForecastAccuracySummary {
  ticker: string
  evaluated_count: number
  newly_evaluated: number
  mean_absolute_error: string | null
  mean_percentage_error: string | null
  direction_accuracy: string | null
  entries: ForecastAccuracyEntry[]
}
