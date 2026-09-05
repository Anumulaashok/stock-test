# Backlog

Backend/infra proposals raised instead of building a frontend workaround, per `docs/MASTER_BRIEF.md` §8 and `docs/AUTONOMY.md` D9/D11/D14. Each entry: what's needed, the concrete shape, why it's not built into the frontend instead.

---

## Markdown report export endpoint (D9)

**Needed:** `render_markdown()` in `app/reporting/markdown.py` is a real, pure formatter over `InvestmentResearchReport` — no calculation, no recommendation, every value already exists on the report — but nothing exposes it over HTTP. Only `ReportService().generate()` (builds the report object) is wired into `/analyze`.

**Proposed shape:** a thin router endpoint, e.g. `GET /api/v1/research/{ticker}/report.md` (or a query param on the existing analyze/report endpoint, `?format=markdown`), returning `text/markdown` — router calls the existing service to get the `InvestmentResearchReport`, then calls `render_markdown()` on it. No new business logic; this is a transport-layer addition per the router-is-thin convention in `CLAUDE.md`.

**Why not built into the frontend:** D9 explicitly says not to add a backend endpoint unprompted for this; rendering markdown from the report client-side would duplicate `render_markdown()`'s logic in TypeScript, which also risks drifting from the backend's actual formatting (I2-adjacent risk even though this isn't a financial figure).

---

## Per-stage source attribution (Wave 4 / D1 Run Inspector)

**Needed:** the source manager already classifies `{provider, via_fallback, source_status, fetched_at}` per fetch at runtime, but it isn't persisted per snapshot stage — so a real Run Inspector (which stage came from which provider, with fallback or not) can't be built without re-deriving this client-side, which would violate I2.

**Proposed shape:** one additive column per snapshot stage row, storing that same object as JSON. Additive only — no alteration of existing columns (D14/D10 constraint pattern).

**Why not built into the frontend:** the data doesn't exist anywhere the frontend can read; re-deriving it in TypeScript would mean guessing at load-time provider behavior, which is exactly the kind of fabricated attribution I1/I2 forbid.

---

## Nightly universe re-analysis job (Wave 2/6 score sparklines + score-efficacy lab; D2/D11)

**Needed:** `/research/ticker` reuses today's run, so a ticker gains at most one snapshot per day and only when a human analyzes it — score history is a function of usage, not time. Score sparklines and the score-efficacy lab both require real score history that doesn't exist yet, and no backfill can produce it honestly.

**Proposed shape (needs quota math before implementation, not included here):**
- A scheduled job re-analyzing the tracked universe on a fixed cadence (nightly, or every N days depending on quota).
- Must measure real per-ticker call counts across all providers first (FMP 250/day, Finnhub 60/min, IndianAPI undocumented, Screener unofficial) before picking a cadence — this is the actual blocker, not engineering effort.
- Staggering across the day/night window to stay under per-minute limits.
- Failure handling: a ticker whose re-analysis fails on a given night should not silently break the sparkline continuity story — needs an explicit gap marker, not an interpolated point.

**Why not built into the frontend:** D11 explicitly forbids substituting a fabricated, sampled, or interpolated version, or drawing a sparkline from two points. There is no honest frontend workaround for missing history — this is a data-generation problem, not a rendering one.

---

## Score-delta attribution endpoint (Wave 4)

**Needed:** decomposing a score change between two runs by sub-score and driving metric (e.g. "Valuation −6: P/E 24.1 → 31.8 on price move, earnings unchanged") requires arithmetic over two snapshots. If that arithmetic can't be avoided by reshaping data the backend already returns, it needs to happen in Python, not TypeScript (I2).

**Proposed shape:** an endpoint taking two `research_run_id`s (or a ticker + two dates) and returning a per-sub-score delta breakdown with the driving metric(s) named, computed server-side from the two snapshots' existing metric values.

**Why not built into the frontend:** computing a score delta and attributing it to a specific metric's change is exactly the kind of statistical/financial computation I2 reserves for the backend.

---

## Per-day DMA50/DMA200 series on the report (Wave 2 price chart)

**Needed:** Screener's per-day DMA50/DMA200 series is already captured in `daily_price_history` (`DailyPriceHistoryRow.dma50`/`.dma200`) but is only consumed by `accuracy_service.py`'s evaluation step, never threaded through to `report.forecast.historical_prices`. Today's price chart can only show a flat "current SMA value" reference line (`forecast.moving_averages`, a single snapshot), not a real moving-average overlay traced across history.

**Proposed shape:** add `dma50: Decimal | None` / `dma200: Decimal | None` to `app/models/market.py`'s `HistoricalPricePoint` (and the corresponding `ReportHistoricalPricePoint` mirror), populated from `daily_price_history` for the same date range already being returned, when available.

**Why not built into the frontend:** computing a 50/200-day moving average from `historical_prices.close` client-side is exactly the statistical computation I2 reserves for the backend — the data already exists in a DB table, it just isn't surfaced.

---

## Historical regime series (Wave 2 "regime bands")

**Needed:** `app/forecasting/ml/regime.py`'s `classify_regime`/`classify_regime_series` classify a row/dataframe into `TRENDING_UP`/`TRENDING_DOWN`/`SIDEWAYS`/etc., but the frontend only ever receives the single *current* regime as a string on `MlForecastResult.regime` (via `fetchMlForecast`) — there is no per-day historical regime series exposed anywhere, which is what "regime bands" (shaded date ranges on the price chart) would need.

**Proposed shape:** an endpoint (or a field added to the ML forecast response) returning `{date, regime}[]` for the ticker's available history, built by running `classify_regime_series` over the same historical feature dataframe the ML pipeline already computes.

**Why not built into the frontend:** there is no honest way to shade historical regime bands from a single current-value string; fabricating a plausible-looking historical band series from one data point would be exactly the kind of synthesized data I1 forbids.

---

## Relative strength vs Nifty as a raw numeric field (Wave 2 "RS toggle")

**Needed:** `app/forecasting/ml/features.py`'s `build_relative_strength_features` computes `relative_strength_14d/30d/90d` against the Nifty 50 benchmark, but this value is only ever consumed internally by the ML pipeline/explanation engine (`explain.py`) to generate driver text — it is never returned as a plottable number in `MlForecastResult` or anywhere else the frontend can read.

**Proposed shape:** expose `relative_strength_30d` (or the full set) as a field on `MlForecastResult`, or a small dedicated endpoint returning the raw series per date for charting as a toggleable line.

**Why not built into the frontend:** there is nothing to plot without this — no raw number reaches the frontend today, only prose mentions inside driver strings.

---

## % change field for deterministic technical methods (Wave 3 method cards)

**Needed:** the Wave 3 method-card spec calls for "target date, projected value, % change, band" per deterministic method. `ReportTechnicalMethod` carries `projected_price`/`formatted_projected_price` but no percent-change-from-current field -- unlike `ReportValuationMethod`, which already has `upside_downside_percent`/`formatted_upside_downside` for the same kind of "how far is this from today" figure.

**Proposed shape:** add `upside_downside_percent: Decimal | None` and `formatted_upside_downside: str | None` to `ReportTechnicalMethod`, computed server-side from `projected_price` and the horizon's current price, mirroring the existing valuation-method pattern exactly.

**Why not built into the frontend:** computing `(projected - current) / current` in TypeScript from two already-known prices is still a derived statistic reserved for the backend (I2) -- it's the same class of violation as computing a moving average, just simpler arithmetic. No uncertainty band exists for any deterministic method at all (there's no per-method equivalent of the ML system's quantile estimates), so "band" is omitted entirely rather than fabricated; there is no proposed shape for that half since none of the underlying methods are probabilistic.

---

## MlForecastPipeline.predict() end-to-end test coverage

**Needed:** `pipeline.py`'s `MlForecastPipeline.predict()` -- the actual serving-time entry point that loads trained artifacts, runs the ensemble, computes analogs/news-impact/quality -- has no direct test exercising its real logic. Existing tests (`test_ml_forecast_api.py`, `test_ml_forecast_cache.py`) only exercise it via a hand-written fake standing in for the whole class, or along degraded/untrained paths.

**Proposed shape:** a test using a real `ArtifactStore` pointed at a temp directory, populated with small trained models (from `train_all_horizons` on a synthetic dataset, mirroring `test_ml_forecast_training.py`'s fixture), then calling the real `MlForecastPipeline.predict()` and asserting the result's horizons/ensemble weights/quality actually reflect what was trained -- not just that the response schema is well-formed.

**Why not done in this slice:** properly faking `MlPriceHistoryService` (async, real yfinance-shaped responses) and `NewsEventIngestionService` together correctly, without either a live network call or a fragile over-mocked test, is more work than the other gaps closed this slice -- flagged rather than rushed.

---

## Run Inspector stage-level provenance (Wave 4)

**Needed:** "which stage blobs exist for a research_run_id, when, with what status" -- the brief's Run Inspector ask. Investigated: per-stage data is split across `RawResearchDataRow`/`ResearchAnalysisSnapshotRow`/`ForecastSnapshotRow`/`LLMAnalysisSnapshotRow`/`ResearchReportSnapshotRow` (all FK'd to `research_run_id`), but no endpoint exposes stage existence/timestamp/status as a structural summary -- `GET /{ticker}/history/{research_run_id}` returns the full `CombinedAnalysisResult`, not a lightweight per-stage manifest.

**Proposed shape:** a `GET /api/v1/research/{ticker}/history/{research_run_id}/stages` endpoint returning `[{stage: str, exists: bool, created_at: datetime | None, status: str | None}]` by checking row existence across the five snapshot tables for that run id -- cheap (existence + one timestamp column per table, no JSON blob deserialization).

**Why not built into the frontend:** there is nothing to reshape -- the structural fact "does this snapshot row exist" isn't present in any response the frontend already receives, and fabricating a plausible-looking stage list would violate I1.

---

## Score-change attribution endpoint (Wave 4)

**Needed:** decomposing a score change between two runs by sub-score and driving metric. Confirmed reachable data for a naive version exists (`ResearchAnalysisSnapshotRow.scoring_json` per run, already used by `/recent`'s windowed query) -- but attributing a delta to "which metric drove it" needs real computation over two snapshots' raw component values.

**Proposed shape:** `GET /api/v1/research/{ticker}/score-delta?from={run_id}&to={run_id}` returning per-category deltas with the specific metric(s) that changed, computed server-side.

**Why not built into the frontend:** per I2 and this session's Wave 3 precedent (declined to compute % change for deterministic method cards for the same reason) -- even a simple subtraction between two backend-returned numbers, when presented as "this is why the score changed," is exactly the derived-statistic class I2 reserves for the backend. `ResearchRunDiffView` (this slice) instead shows both runs' raw values side by side with equality-based highlighting only -- never a computed delta.

---

## Universe-relative score percentiles (Wave 4)

**Needed:** "score 74 puts this ticker in the 82nd percentile of the tracked universe." No existing table/service computes this -- `SectorRankingService` recomputes sector averages live via the full analysis pipeline (not from persisted snapshots), and nothing ranks one ticker's score against others'.

**Proposed shape:** a service reading each tracked ticker's latest `ResearchAnalysisSnapshotRow.scoring_json.overall_score` (the same set `/recent`'s windowed query already assembles) and computing a percentile rank, exposed via a small new endpoint or an additional field on an existing report/summary response. Must be labeled "tracked universe," not "sector" or "market" (no peer/sector multiple source exists here) -- and must carry the cohort's `n`.

**Why not built into the frontend:** this is a real cross-ticker statistical computation (a percentile rank requires the full distribution, not just one ticker's own data) -- squarely backend work, not reshaping.

---

## Screener: sector/sub-score/fundamental filters and true universe scale (Wave 5)

**Needed:** the master brief's Screener asks for filtering/sorting by sector, sub-scores, and computed fundamentals across "the universe." The only existing endpoint usable without new backend work, `GET /api/v1/research/recent`, returns `{ticker, company_name, overall_score, band, research_date, status}` -- no sector, no sub-score breakdown, no fundamentals -- and is capped at `limit<=100` (`app/api/research.py`), and by definition only covers tickers that have *already* been researched at least once (not the full listed universe).

**Proposed shape:** a dedicated screener-listing endpoint reading persisted per-category scores (already computed and stored in `ResearchAnalysisSnapshotRow.scoring_json` per run) plus sector metadata (`app/sectors/universe.py`'s `SECTOR_UNIVERSE`), joined and paginated server-side, with sector/sub-score/fundamental-threshold query params.

**Why not built into the frontend:** sector and sub-score data isn't in any response the frontend can already read for the full universe; fabricating sector membership or sub-scores client-side would violate I1. Shipped the honest, real version instead: filter/sort/CSV over the 100 tickers `/recent` actually returns, explicit copy stating this is "the most recently researched tickers this app already tracks -- not the full listed universe."

---

## Saved screens with a change feed (Wave 5)

**Needed:** persisting a named filter combination and showing entries/exits/rank moves between runs -- requires server-side storage (a new table, user-scoped, following the `AlertRow`/D10 pattern) and a comparison job between two point-in-time screener snapshots.

**Why not built into the frontend:** genuine new persistence, not reshaping. Not built this session; the current Screener has no save/history concept at all, only live filter/sort of the current `/recent` snapshot via URL params.

---

## Portfolio value-over-time chart (Wave 6)

**Needed:** a chart of total portfolio value across time, the natural companion to the current point-in-time summary. No historical portfolio-value snapshots exist -- `HoldingRow` only carries the current quantity/average_cost, and reconstructing past value from holdings' historical prices would misrepresent it (a holding added last week would show as "held" at last year's price, which never actually happened) and requires combining multiple tickers' historical prices into one series, which is new arithmetic either way.

**Proposed shape:** a daily portfolio-value snapshot taken whenever holdings change (or via an end-of-day job), stored per-user, exposed via `GET /api/v1/portfolio/history`.

**Why not built into the frontend:** no real snapshot history exists to reshape; anything shown today would have to be synthesized (I1) or silently wrong about when holdings were actually added (I1's spirit).

---

## Portfolio weighted score, sector concentration %, risk-band exposure % (Wave 6)

**Needed:** a portfolio-level weighted overall score, "40% of holdings by value are in Financials," and "60% of the book sits in Speculative-band tickers."

**Proposed shape:** a `GET /api/v1/portfolio/composition` endpoint combining each holding's market value (already computed server-side per holding) with its latest score/band/sector (from `ResearchAnalysisSnapshotRow`) and `SECTOR_UNIVERSE`, returning the weighted aggregates with the underlying `n` and total value.

**Why not built into the frontend:** a weighted average across holdings is new arithmetic over multiple already-backend-computed numbers (I2) -- distinct from the topContributors/topDetractors sort already shipped this slice, which never combines two holdings' figures into a new one.

---

## Portfolio XIRR and max drawdown (Wave 6)

**Needed:** the two return metrics an active portfolio page implies -- money-weighted return accounting for cash-flow timing (XIRR) and peak-to-trough decline (max drawdown).

**Proposed shape:** both need a real cash-flow/value time series first (see the value-over-time backlog item above) plus a correct XIRR solver (iterative, not closed-form) and a drawdown scan over that series -- backend-only regardless of the missing-history gap, since both are genuinely new derived statistics over multiple time points, not a reshape of one.

**Why not built into the frontend:** blocked on the same missing history as the value-over-time chart, and even with history present, XIRR/drawdown are new computed statistics (I2), not sorting or filtering.

---

## Holdings correlation / overlap (Wave 6)

**Needed:** "these two holdings move together" or a concentration warning based on how correlated the book's positions are.

**Proposed shape:** a `GET /api/v1/portfolio/correlation` endpoint computing pairwise correlation coefficients from each ticker's persisted daily price history (`DailyPriceHistoryRow`), returned as a matrix with each pair's sample size `n`.

**Why not built into the frontend:** a correlation coefficient is a new statistic computed from two price series -- squarely I2 backend-only, and needs `n` surfaced per I9 (thin history between two tickers must gate the figure, not silently compute one from 5 overlapping days).

---

## Bulk analyze queue with remaining-quota display (Wave 7)

**Needed:** a queue for analyzing many tickers at once, surfacing remaining quota before queuing more.

**Proposed shape:** a `GET /api/v1/quota` (or similar) endpoint exposing the actual per-key/per-window call budget and current usage the source manager already tracks internally, plus a queue-status endpoint if queuing is meant to survive a page reload.

**Why not built into the frontend:** no real quota figure exists anywhere the frontend can read today (`grep -rn quota app` turns up only a code comment and a config default, not a tracked counter) -- a "remaining quota" figure shown without one would be fabricated (I1). A queue UI with no real quota to display would either lie about capacity or omit the very thing this feature is supposed to communicate.

---

## Watchlist notes/tags/conviction (Wave 7)

**Needed:** free-text notes, tags, and a conviction rating per watchlist item, included in the CSV export.

**Proposed shape:** additive columns (or a child table) on `WatchlistItemRow` -- `notes: str | None`, `tags: list[str]`, `conviction: int | None` -- plus `PATCH /api/v1/watchlist/{ticker}` to write them. Same additive-migration shape as D10's Alerts tables.

**Why not built into the frontend:** `WatchlistItemRow` has no such columns today: this is schema/persistence work, not a reshape of an existing response, and isn't yet covered by an equivalent to D10's explicit authorization for Alerts.

---

## Ask Stock Agent scoped to portfolio/screen/comparison (Wave 7)

**Needed:** the master brief asks for "Ask Stock Agent" to answer questions grounded in a portfolio, a screener result set, or a comparison -- not just a single ticker's research, which is all it does today.

**Proposed shape:** `app/api/qa.py` currently exposes only `ask_ticker_question` (one ticker's persisted research as grounding context). A portfolio/screen/comparison-scoped variant needs its own context-assembly logic -- e.g. `POST /api/v1/qa/portfolio` gathering the caller's holdings + each one's latest snapshot, or `POST /api/v1/qa/screen` gathering the current filtered result set's rows -- each citing which rows/metrics grounded the answer, the same way the ticker-scoped version already cites its research run.

**Why not built into the frontend:** there is exactly one Q&A endpoint (`ask_ticker_question`), and it only accepts a ticker. Answering a portfolio/screen/comparison-scoped question would mean either fabricating grounding client-side (I1) or silently reusing the single-ticker endpoint in a way that doesn't actually reflect the multi-row context the user is looking at.

---

## Not backlog — resolved

**Alerts backend** (originally Wave 4/5 backend request) is **authorized** under `docs/AUTONOMY.md` D10 (additive tables only, `app/portfolio/service.py` pattern, evaluate-on-read). This is Wave 5 build scope, not a backlog proposal.
