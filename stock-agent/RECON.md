# Phase 0 Recon — Build Brief v2

Branch: `feature/stock-intelligence-redesign`. Answers below are sourced by reading the actual files, not inferred.

## 1. Is `MlForecastPanel.tsx` wired in?

**Yes, already wired.** `frontend/src/routes/stock/ForecastTab.tsx:3,9` imports and renders it above the existing deterministic forecast section:

```tsx
<MlForecastPanel ticker={ticker} historicalPrices={report.forecast?.historical_prices ?? []} />
<div>
  <h3>Technical Baseline</h3>
  <ForecastSection forecast={report.forecast} market={report.market} />
</div>
```

This already satisfies I7 structurally (separate block, separate label "Technical Baseline" vs. the ML panel above it) — needs verification against live responses, not re-wiring. **Wave 1's "wire the panel" item is done; redirect that effort to items 2–5 in the unexposed-surface table** (accuracy panel, analogs, news-impact, data-source health badge) which have no UI yet.

## 2. `ForecastLineChart.tsx` state

Chart.js **v4 UMD-style tree-shaken registration** (`Chart.register(CategoryScale, LinearScale, LineController, LineElement, PointElement, Filler, Tooltip, Legend)` at module scope, `frontend/src/components/ForecastLineChart.tsx:15`). One wrapper component already exists but is **not yet the generic `<PriceChart>` from the brief** — it's forecast-specific (`historical`/`predicted`/`markers`/`referenceLines`/`band` props), no DMA-overlay or volume-subchart concept, no candlestick mode, no provenance-driven mode switch. It already does the right things worth reusing: shared date-axis alignment with `null` gaps (never interpolates — satisfies I1/I8 discipline), destroys/rebuilds the chart instance on prop change, `role="img" aria-label`. **Confirms the brief's framing: extend this pattern into a generic `<PriceChart>`, don't introduce a second charting approach.**

## 3. `StockLayout.tsx` / `SideNav.tsx` in-flight state

Both are **new files on this branch** (`git diff main...HEAD` shows them as `new file mode`), with further **uncommitted** edits on top (`git status`: `M` for both). Current `SideNav.tsx` nav items: Intelligence, Discover, Watchlist (auth), Portfolio (auth), Research, Settings (auth) — plus a locked "coming soon" list: **Screener, Alerts, News** (exactly the three Wave 5 nav items the brief expects to unlock). `StockLayout.tsx` fetches the report once via `StockReportProvider`, renders loading/error(409-aware)/empty/ready states itself, and only mounts `<Outlet/>` (the tab content) once ready — tabs never re-handle these states. **Coordinate:** any Wave 1 header/status-badge work should slot into `StockHeader` (rendered here) rather than duplicating fetch logic; don't touch `StockLayoutInner`'s state machine.

## 4. Response shapes — `/ml-forecast/*`

Full Pydantic models read directly from `app/models/ml_forecast.py` and `app/api/ml_forecast.py`. Mirror these as TS types verbatim (don't hand-derive from sample JSON):

- **`GET /{ticker}` → `MlForecastResult`**: `{ ticker, generated_at, data_date, current_price, regime, horizons: Record<string, MlHorizonForecast>, news_impact: NewsImpactSection, data_quality: DataQuality, model_version, feature_version, news_model_version, warnings: string[] }`
- **`MlHorizonForecast`**: `{ horizon, target_date, current_price, expected_return, expected_price, quantiles: QuantileEstimate, probability_positive, forecast_quality, quality_score, quality_reasons: string[], model_agreement, model_outputs: ModelAgreementEntry[], drivers: {positive_drivers, negative_drivers}, analog: AnalogSummary, historical_accuracy: HistoricalAccuracy | null, change_from_previous: dict | null }`
- **`QuantileEstimate`**: `{ p10, p25, p50, p75, p90 }` all nullable
- **`ModelAgreementEntry`**: `{ model_name, point_return, weight }` — this is the per-model contribution + inverse-MAE weight the brief wants surfaced; weight `0` means "no valid walk-forward result," per-model, not blended
- **`AnalogSummary`**: `{ sample_size, is_reliable, positive_rate, negative_rate, mean_return, median_return, quantiles }`
- **`HistoricalAccuracy`**: `{ sample_size, mae, rmse, directional_accuracy, brier_score, interval_coverage_80 }`
- **`DataQuality`**: `{ price_history_days, fundamentals_available, news_available, regime, training_data_end_date }`
- **`NewsImpactSection`**: `{ recent_events: RecentNewsItem[], historical_statistics: NewsImpactEventSummary[], data_available: boolean, note: string | null }`
- **`GET /{ticker}/history`**: `{ ticker, predictions: [{ prediction_timestamp, horizon, predicted_return, predicted_price, target_date, actual_return, actual_price, direction_correct, forecast_quality, model_version }] }` — this is the prediction-vs-actual feed for the Wave 3 flagship chart
- **`GET /{ticker}/accuracy`**: `{ ticker, accuracy_by_horizon: { [horizon]: { sample_size, mae?, rmse?, directional_accuracy?, brier_score?, interval_coverage_80? } | { sample_size: 0, note: "No walk-forward evaluation recorded yet" } } }` — **the zero-sample case is a distinct shape, not just zeros**; the accuracy panel must render that as "no evaluation yet," never as a 0% accuracy figure
- **`GET /{ticker}/news-impact`**: same shape as `MlForecastResult.news_impact` (`NewsImpactSection`)
- **`GET /{ticker}/analogs`**: `{ ticker, analogs_by_horizon: { [horizon]: AnalogSummary } }`

## 5. `/research/{ticker}` family + snapshot lineage depth

Endpoints confirmed in `app/api/research.py`: `POST /ticker`, `GET /recent`, `GET /{ticker}`, `GET /{ticker}/progress`, `GET /{ticker}/history`, `GET /{ticker}/history/{research_run_id}`, `GET /{ticker}/predictions`.

**Snapshot lineage is shallow — value only, not per-metric formula/source.** `ResearchAnalysisSnapshotRow` (`app/db/models.py:215`) stores whole-blob JSON dumps per run: `financial_analysis_json`, `valuation_json`, `scoring_json` — entire Pydantic `model_dump_json()` outputs, one row per run. `ResearchReportSnapshotRow` stores the entire assembled `CombinedAnalysisResult` the same way. There is **no column carrying a per-field provenance/formula record** (no `metric → {source, formula, inputs}` table). The one exception: `ForecastSnapshotRow` does carry per-method `metadata_json` (reason/r_squared/status) and explicitly persists *unavailable* rows rather than dropping them.

**Implication for Wave 4's lineage drawer:** day-one depth is "which run produced this JSON blob and when," not "which named inputs computed this exact field." A true per-metric formula drawer would require either (a) a new backend column/table recording provenance at write time, or (b) client-side re-deriving field-level lineage from the whole-blob diff — which risks re-computing in TypeScript (I2 violation) if not done carefully. **Recommend flagging this as a backend-shape request (§10 rule 5 in the brief) rather than building a fake-granular drawer client-side.** The drawer is still buildable today at the *stage* level (raw financial data → valuation → scoring → forecast → report, each as one named blob with its `created_at` and `research_run_id`), which is real value and matches what rows 1-2 in the unexposed-surface table need.

## 6. Score history depth (gates sparklines)

**No dev database exists in this checkout** (`*.db` glob returned nothing — SQLite is created on first run). Cannot report real per-ticker snapshot counts; anything else would be a fabricated number, which I9 explicitly forbids doing to the user, let alone to myself. **Action:** before building score sparklines (Wave 2) or the score-efficacy lab (Wave 6), query the actual dev/staging DB (`SELECT ticker, COUNT(*) FROM research_runs WHERE status IN ('COMPLETED','PARTIAL') GROUP BY ticker ORDER BY 2 DESC`) and report real counts. Until then, treat sparklines as **provisionally deferred** per the brief's own instruction ("if history is three runs deep, defer and say so").

## 7. Tailwind v4 theming

**Not `@theme`-based — plain CSS custom properties on `:root`** in `frontend/src/index.css` (no `frontend/src/**/*.css` uses the Tailwind v4 `@theme` directive at all; only one CSS file exists in the project). Tokens are centralized and consistently consumed via `var(--color-*)` / `var(--radius-*)` / `var(--shadow-*)` across components (confirmed in `SideNav.tsx`'s Tailwind arbitrary-value usage like `bg-[var(--color-accent-soft)]`). This is good news for Wave 8 (light theme): **tokens are centralized in one place**, so a light theme is "redefine ~15 custom properties once," not "hunt hardcoded hex across dozens of files" — Wave 8 is viable, contrary to the brief's fallback-skip clause. Not a `@theme` block specifically, but functionally equivalent (single source of truth) for this purpose.

## 8. Auth + persistence for alerts/saved screens

**Confirmed: JWT + `app/portfolio/service.py` is the real, user-scoped server persistence path.** Every method takes `user_id` explicitly (`list_holdings`, `add_holding`, `list_watchlist`, `add_to_watchlist`, `list_watchlist_enriched`, etc.), backed by `PortfolioRow`/`HoldingRow`/watchlist tables, auth via `app/auth/dependencies.py:get_current_user`. **Alerts and saved screens (Wave 5) should follow this exact pattern** — new tables + a service module scoped by `user_id`, never `localStorage`. No existing `alerts` or `saved_screens` module yet; that's genuinely new backend surface, not something already built and hidden.

## 9. `../reliance_ns_lstm_project/` and `../stock-agent-forecasting/`

**Neither is wired into this repo — no imports, no references, nothing in `app/` or `frontend/` points at them.**

- `../reliance_ns_lstm_project/`: a **standalone Keras/TensorFlow project** — 2-layer LSTM trained on 5 years of RELIANCE.NS daily closes via yfinance, producing daily/weekly/monthly recursive forecasts with its own README, `saved_models/`, `notebooks/`, separate `requirements.txt`. Explicitly "no LLM anywhere in this pipeline." This looks like a prior/parallel experiment for the same forecasting problem `app/forecasting/ml/` now solves natively in-repo with a different architecture (ensemble of naive/RF/GBM-quantile/historical-analog, not LSTM).
- `../stock-agent-forecasting/`: has its own separate `.git`, and nests a `stock-agent/` subdirectory inside it — likely an earlier clone/fork of this same repo used for forecasting experiments before the work landed on this branch as `app/forecasting/ml/`.

**Per the brief's own instruction ("ask the user; do not merge them unprompted"): flagging this, not merging.** Best guess is both predate and were superseded by the in-repo `app/forecasting/ml/` ensemble subsystem, making them safe to leave untouched or archive — but that's a guess, not something to act on silently.

---

## Prioritized plan for Wave 1 (pending approval)

Given #1 is already done, Wave 1 becomes:

1. **Accuracy panel + prediction-history feed** for the ML forecast — `/history` and `/accuracy` are live endpoints with zero frontend today; highest-credibility win per the brief, and the shapes are now fully typed (§4 above). Ship the §4.5 synthetic-data tripwire test alongside this, not as a separate task. **Done** (`MlAccuracyPanel.tsx`, `AccuracyScatterChart.tsx`).
2. **News-impact and analogs sections** in `MlForecastPanel` — **done** (`NewsImpactPanel.tsx`, `AnalogPanel.tsx`). **No standalone `/news-impact` or `/analogs` fetch was added.** `MlForecastResult` (already fetched once by `MlForecastPanel` via `fetchMlForecast`) embeds `news_impact` at the top level and `analog` inside every `MlHorizonForecast` — confirmed by reading `app/models/ml_forecast.py`: `NewsImpactSection` and `AnalogSummary` are the exact same Pydantic models the two standalone endpoints (`GET .../news-impact`, `GET .../analogs`) return. Both new panels are pure presentational components fed from that single already-loaded `result`, not independent `useAsync` fetches — one request continues to serve the chart, chips, details, news-impact and analog surfaces together. The two standalone endpoints remain useful for any future caller that wants *only* news or *only* analogs without the rest of the forecast payload, but nothing in the frontend needs them today.
3. **Data-source health badge — sidebar footer, not the ticker-scoped `StockHeader`.** Source health is global state (which provider chain is live, whether the Screener session is expired), visible on every route including Discover/Portfolio/Settings, not just `/stock/:ticker`. The Sept 5 sidebar-footer cleanup commit (`chore(nav): remove decorative quote card from sidebar footer`) vacated exactly this slot — persistent, app-wide, otherwise-unfinished-looking. `GET /api/v1/market/data-sources/status` already returns everything needed (`configured`/`status`/`primary_for`/`fallback_for`/`limitation` per source, `app/models/market_history.py:108`): compact in the footer, expanding to per-provider detail on click, `AUTH_EXPIRED` linking straight to the session-cookie control. `StockHeader` keeps only ticker-scoped badges: exchange, session state, freshness/provider tag for that ticker's own data.
4. **Markdown report export** button on stock detail from `app/reporting/` (not yet checked in this recon pass — needs a quick endpoint confirmation before wiring).
5. **CSV export** for Watchlist/Portfolio via one shared `toCsv` helper.

Not doing: re-wiring `MlForecastPanel` (already wired), inventing per-metric lineage depth beyond stage-level and the Forecast tab's per-method `ForecastSnapshotRow.metadata_json` (needs a backend `source_attribution_json` addition first), score sparklines / score-efficacy lab (blocked on a nightly universe re-analysis job that doesn't exist yet — usage-driven snapshot cadence, not a data-volume problem), a candlestick chart mode (cut — Chart.js has no native support and only one provider has real OHLCV), touching the sibling ML directories (owner's call pending, leave as-is).

Items 1 and 2 are approved and starting now.
