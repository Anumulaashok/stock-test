# Progress

Rewritten after every slice. Current wave, current slice, what's committed, what's in flight, what's blocked.

**Push status: blocked, 33 commits unpushed** (as of the Wave 4 boundary, 2026-09-05; retried at this boundary per the once-per-wave policy, still 403 -- same credentials issue, user is fixing on their end). `git push origin feature/stock-intelligence-redesign` fails with a 403 (permission denied for the configured git credentials against `Anumulaashok/stock-test.git`) -- a credentials issue on the user's end, being fixed there, not fixable from this session. **Retry policy: once per wave boundary, not per slice** (per explicit instruction) -- so this count should only update at wave boundaries, not every commit. If a rate-limit gap ends this session before it's resolved, all commits below exist only on this machine -- check `git log --oneline origin/feature/stock-intelligence-redesign..HEAD` for the current unpushed count before assuming anything is on the remote.

## Current wave

**Wave 1 — complete and committed. Wave 2 in progress.**

Operating mode: in-session, report-and-wait at wave boundaries, commit and push only on explicit user ask (per `docs/MASTER_BRIEF.md`'s own commit policy and the user's explicit choice on 2026-09-05 to run this way rather than the full unattended `docs/AUTONOMY.md` §3/§5 infrastructure). User confirmed 2026-09-05: commit the pending Wave 1 slice, proceed into Wave 2.

## Committed

- `0df2f47` — StockLayout force-refresh computing fix + regression test
- `fea0491` — sidebar quote-card removal
- `6fc0310` — chore(ml-forecast): pre-existing ML subsystem tracked unchanged
- `42a94fb` — feat(ml-forecast): accuracy panel + prediction-vs-actual scatter (Wave 1.1)
- `29aff19` — test: synthetic-data tripwire
- `bb54860` — chore(dev): fixture route for ML panel states
- `b100005` — fix(ml-forecast): empty-state wording + scatter marker contrast (found via fixture eyeballing)
- `e1511a2` — feat(ml-forecast): news-impact and analogs panels (Wave 1.2)
- `2a09c17` — docs: RECON.md news/analogs endpoint-reuse decision
- `9ef8d8e` — chore: track pre-existing .gitignore var/ entry
- `f13baea` — docs: add master execution brief and autonomy contract
- `9c996b4` — feat(data-sources): dedupe status fetch, add sidebar health badge (Wave 1.4)
- `4cf7b2e` — chore(dev): fixture route for data-source health badge states
- `d4cbd66` — feat(watchlist,portfolio): CSV export (Wave 1.6)
- `e443f03` — docs: add PROGRESS/DECISIONS/BACKLOG/BLOCKED tracking files

**Wave 1.5 — Markdown export: dropped, not built.** See `BACKLOG.md`.

**Wave 1 is complete.** Verification floor at close: 258/258 vitest, `tsc -b` clean, `oxlint` clean (no new warnings beyond the pre-existing pattern), `vite build` clean, both dev fixture routes (`/__dev/ml-panels`, `/__dev/health-badge`) confirmed absent from `dist/`. Not yet pushed (push still requires explicit ask).

## In flight

**Wave 2, slice 1 — done, not yet committed.** `<PriceChart>` extraction (D4) + price chart on Technical/Overview:

- `ForecastLineChart.tsx` renamed `PriceChart.tsx` (git mv), generalized: parameterized `ariaLabel`, new optional `volume` prop rendering a bar sub-chart sharing the same date domain. Note: `ForecastLineChart` already had 2 real callers before this slice (`ForecastSection`, `MlForecastPanel`) — the extraction gate was already satisfied; Technical/Overview become the 3rd/4th.
- New `PriceChartSection.tsx` (shared by `TechnicalSection` and `OverviewTab` from the start — 2 real callers, no premature abstraction): close price + volume sub-chart from `report.forecast.historical_prices` (already on the report, no new fetch), a `CrossoverBadge` reading `forecast.crossover.signal` directly (new addition to `SignalBadge.tsx`), and current-SMA50/200 flat reference lines (NOT a moving overlay — see below), with an honest empty state linking to Settings → System → Import Historical Data when there's no price history.
- **Found via investigation, not yet built:** the brief assumed DMA50/200 "overlays are a fetch, not a computation" — false. Screener's per-day DMA series lands in `daily_price_history` but is never threaded to `report.forecast`; only a current-value SMA snapshot is on the report. Shipped the honest version (flat current-value lines, clearly labeled); filed 3 `BACKLOG.md` proposals (per-day DMA series, historical regime series, RS raw numeric field) since none of Golden/Death-cross-badge's siblings — regime bands, RS toggle — have real data to plot yet. See `DECISIONS.md` entries from this slice.
- New dev fixture route `/__dev/price-chart` (7 states: golden/death/neutral/no crossover, volume on/off, no-SMA, empty), eyeballed — no issues found.
- Verification floor: 269/269 vitest, `tsc -b` clean, `oxlint` clean, `vite build` clean, all three dev fixture routes confirmed absent from `dist/`.

**Wave 2, slice 2 — done, not yet committed.** User-caught fix + resolved-prediction overlay:

- **G3 fix:** the slice-1 SMA reference lines were a real defect (full-width line at a current-only value implies false historical crossings, arguing against `CrossoverBadge`). `PriceChart.tsx` gained `edgeMarkers` (short right-edge stub, no full-width line); `PriceChartSection.tsx` switched to it. Named the anti-pattern ("current-value-as-full-width-line") in `DECISIONS.md` for future metrics. One known remaining instance (`ForecastSection.tsx`'s `HorizonChart`) flagged but not touched -- pre-existing code, not written this session.
- `docs/MASTER_BRIEF.md`'s Wave 2 DMA claim corrected in place, pointing at the `BACKLOG.md` entry.
- **Resolved-prediction overlay** (Wave 1's deferred secondary view): `MlForecastPanel.tsx` now fetches `fetchMlForecastHistory(ticker, selectedHorizon, 200)` (same endpoint the accuracy panel already uses -- local DB read, not metered) and plots each already-resolved prediction's predicted price as an amber marker on the AI forecast chart, alongside the real historical/predicted lines. Pending predictions correctly excluded (nothing to compare yet).
- Eyeballed on `/__dev/ml-panels`'s new fixture section: amber markers clearly distinguishable from the gray historical line and blue predicted/band region; a materially-wrong past prediction visibly separates from the real price line.
- Verification floor: 275/275 vitest, `tsc -b` clean, `oxlint` clean, `vite build` clean, all fixture routes confirmed absent from `dist/`.

**Push status:** all commits through this slice are local only. `git push origin feature/stock-intelligence-redesign` fails with a 403 (permission denied for the configured git credentials, `Ashok-Raga`, against `Anumulaashok/stock-test.git`) -- a credentials/access issue outside what this session can fix. Flagged to the user; retried once after the first failure, not retried further.

**Wave 2, slice 3 — done, not yet committed.** Signal card:

- New `SignalCard.tsx` atop `OverviewTab`: score bar (color by band), band pill, top-1 positive/watch item (analyst-first, category-reason fallback -- same pattern `WhyThisScore` uses, duplicated locally rather than refactoring that pre-existing file without being asked), coverage ("N/M inputs" from `scoring.categories[].status`), and a provenance line (`market.source`/`.freshness`/`.market_timestamp`) -- all reshaped from `report`, no new fetch.
- **No regime badge** -- deferred alongside regime bands/RS per explicit instruction; logged in `DECISIONS.md` (same ML-only data source either way).
- Eyeballed on new `/__dev/signal-card` fixture route (5 states). One near-miss: a screenshot appeared to show a bug (fallback content rendering when it shouldn't), but a direct DOM-content dump proved the component was correct throughout -- the screenshot was misread, not a defect. Recorded as a caution about trusting a single screenshot glance over ground truth when they'd disagree.
- Verification floor: 283/283 vitest, `tsc -b` clean (one real type error caught and fixed: `toDisplayNumber` returns a formatted string, not a number -- needed a separate numeric parse for the bar-width calculation), `oxlint` clean, `vite build` clean, all 4 fixture routes confirmed absent from `dist/`.

## Wave 3 (in progress)

**Slice 1 — deterministic section, done, not yet committed.** Per explicit sequencing instruction (deterministic before ML, since it carries the permanent "not backtested" label):

- `ForecastSection.tsx` gained a persistent "Not backtested" badge in its header (visible regardless of horizon tab) and a new 4-card row (`buildMethodCards`/`MethodCard`/`MethodCardRow`) showing all deterministic methods (`linear_regression`, `sma_50`, `sma_200`, `sma_crossover_momentum`) side by side, parallel, never averaged (I6) -- each card shows target date + projected value, or an honest unavailable+reason state.
- **No % change, no band** on the cards -- neither exists on `ReportTechnicalMethod` (only `ReportValuationMethod` has an upside/downside percent); computing % change from two known prices in TS would still be a derived-statistic I2 violation. Filed in `BACKLOG.md`; logged in `DECISIONS.md`.
- Confirmed `technical_methods` (not `price_trend`) is the right source for all 4 cards including `linear_regression` -- a separate backend computation from the chart's own dashed line, correctly left unmerged.
- New fixture route `/__dev/forecast-section`, eyeballed (including tab switching) -- clean, one pre-existing (not-this-slice) minor visual overlap noted (an "other technical methods" marker sitting near the new edge-marker stub for the same SMA value) but not touched, out of scope.
- Verification floor: 288/288 vitest, `tsc -b` clean, `oxlint` clean, `vite build` clean, all 6 fixture routes confirmed absent from `dist/`.

**Slice 2 — ML section, done, not yet committed.**

- `HorizonChip` now shows an explicit "LOW" text badge (not just a colored dot) whenever `forecast_quality === 'LOW'` -- visible on the collapsed chip, satisfying I10's "not a quieter footnote."
- New `isNaiveOnlyFallback()` detects when every `model_outputs` entry is `naive_zero_return` (the backend's own "no trained artifacts" degradation path, `app/forecasting/ml/pipeline.py`) and renders the whole chip with a red border/background plus an explicit "NAIVE FALLBACK ONLY" label -- unmistakable, not hidden behind the "Why?" expand.
- `DetailsPanel`'s per-model chips now show each model's `weight` (inverse walk-forward MAE); `weight === 0` renders as "weight 0 (no valid walk-forward result)" with a red border, never a bare "0%" that reads as a rounding artifact.
- Added "80% interval coverage" next to the p10-p90 range in `DetailsPanel`, sourced from `forecast.historical_accuracy.interval_coverage_80` -- already embedded in the already-fetched `MlForecastResult`, no new fetch (G5).
- Analogs/news-impact were already integrated in Wave 1 and drivers already existed pre-session; neither duplicated.
- 4 new fixture sections added to `/__dev/ml-panels` (HIGH quality, LOW quality + weight-0, naive-only fallback, interval-coverage-not-yet-available), eyeballed -- all render correctly, no issues found.
- Verification floor: 295/295 vitest, `tsc -b` clean, `oxlint` clean, `vite build` clean, all fixture routes confirmed absent from `dist/`.

## Execution mode change (2026-09-05)

Switched from "report each wave, wait" to **full autonomous, never-pause** per explicit user instruction, following a large new "build a real ML forecasting system" brief's STEP 40-47. See `docs/CONTINUOUS_RUN.md` for the adapted protocol, and `DECISIONS.md` for the reasoning (including two prior user instructions that still take precedence: push once per wave boundary not per slice, and established commit granularity).

**Critical finding before any new ML code was written:** investigated the existing `app/forecasting/ml/` subsystem (33 files) instead of assuming the brief's "build from scratch" framing was accurate. It already implements almost everything asked: real expanding-window walk-forward validation, real leakage prevention, a full 30-category news taxonomy with dedup/novelty/event-study (abnormal return vs. benchmark), and a real inverse-walk-forward-MAE ensemble. 78/78 `test_ml_forecast_*` tests were passing -- **but the entire Python backend (33 files + 3 more + 13 test files, 47 files total) had never actually been committed to git**, despite an earlier commit this session (`6fc0310`) claiming to. Fixed: committed the real pre-existing snapshot (`2222845`), verified via diff that it contained none of this session's later ML edits.

Real gap identified: only 2 of the brief's requested model families were missing (ARIMA/AutoReg, LightGBM/XGBoost). User approved adding `statsmodels`/AutoReg (done, commit `5e01a31` -- also caught and fixed a real bug, `AutoReg(old_names=False)` not valid in the installed statsmodels 0.15, via actually running the CLI against DANLAW rather than trusting green unit tests alone). User declined LightGBM/XGBoost (system `libomp` dependency, marginal expected gain over the existing sklearn `HistGradientBoostingRegressor`).

**Also found and fixed:** `training.py`'s `train_all_horizons()` and `pipeline.py`'s `MlForecastPipeline.predict()` had zero direct test coverage (only exercised via fakes/degraded paths in `test_ml_forecast_api.py`/`test_ml_forecast_cache.py`). Added `tests/test_ml_forecast_training.py` (6 tests, synthetic dataset with a genuinely learnable relationship, confirms a real model beats naive baseline via walk-forward MAE -- not just "the code runs").

**Environment fact worth recording:** no local database file exists in this dev environment (`stock_agent.db` absent) -- `forecast_predictions`/`forecast_model_performance`/`news_events` have zero rows here. The architecture and logic are real and tested; populated historical data would only exist wherever training/ingestion jobs have actually been run (possibly a different environment). Running a full-universe `--train` job here would mean real yfinance calls across the whole sector universe -- not done without narrower instruction, since it's a materially larger and slower action than the single-ticker DANLAW check already run.

## Wave 4 (Provenance) -- slice 1, done, not yet committed as of this line (see commits below once written)

Investigated the research-run/snapshot data model before building anything. Found: a per-ticker Research History list + single-run viewer (`ResearchHistorySection.tsx`, `?run=` param) **already existed** and already used the `/history`/`/history/{research_run_id}` endpoints -- an earlier investigation pass this turn had incorrectly reported nothing consumed `/history`; corrected after actually reading the component. Real gap: no run-to-run **comparison**.

Built: `researchRunDiff.ts` (pure `buildRunDiffRows`, equality-only comparison, never a computed delta -- I2), `ResearchRunDiffView.tsx` (side-by-side table, "Changed" flag only), wired into `ResearchHistorySection.tsx` as a checkbox-select-two-runs-then-compare flow using the two already-existing endpoints (no new fetch). 12 new tests (4 pure-function + 8 component-level, including the "no saved report" degraded case). 302/302 frontend tests, `tsc -b`/`oxlint`/`vite build` clean.

Three other Wave 4 asks (Run Inspector's stage-level provenance, score-change attribution, universe-relative percentiles) all turned out to need genuine new backend computation not covered by any existing endpoint -- filed as 3 `BACKLOG.md` proposals rather than approximating any of them client-side. Coverage-on-signal-card was already done in Wave 2.

Did not do a dedicated fixture-route screenshot for this slice (G7) -- the new markup reuses the exact table/`surface-card` styling already shipped and visually verified elsewhere in this same file; noting the exception explicitly rather than silently skipping the step.

---

**Not yet done from the new brief:** `MlForecastPipeline.predict()` still has no direct end-to-end test (only via fakes) -- flagged as a remaining gap, not silently skipped (see `BACKLOG.md`). Frontend Step 29 page structure -- largely already matches (Waves 1-3 built accuracy panel, news impact, analogs, quality/weight visibility, resolved-prediction overlay); a section-by-section audit against the exact Step 29 layout hasn't been done yet.

**Wave 4 is now functionally complete** (research-run diff built; the other 3 asks correctly deferred to `BACKLOG.md` as genuine backend gaps; coverage-on-signal-card already existed from Wave 2). Continuing to Wave 5 next: Alerts backend is D10-authorized (additive tables, `app/portfolio/service.py` pattern, evaluate-on-read) -- starting there since it's clearly pre-approved, ahead of Screener/Comparison/News frontend work which hasn't been scoped this session.

---

**Wave 3 is now functionally complete** (deterministic section built first per sequencing instruction, then the ML section, never sharing a container -- I6/I7 held throughout).

---

**Wave 2 is now functionally complete** (D4 extraction, price chart + DMA/crossover/volume on Technical+Overview, resolved-prediction overlay, signal card). Regime bands, RS toggle, and the signal card's regime badge all correctly deferred, not fabricated. Score sparklines correctly unbuilt (D2/D11). Nothing in this wave committed yet beyond the earlier-pushed slice-1-fix commits.

## Blocked

Nothing yet. See `BLOCKED.md` (currently empty).

## Not started

Waves 3–8 in full, per `docs/MASTER_BRIEF.md` §6.
