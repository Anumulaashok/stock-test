# Progress

Rewritten after every slice. Current wave, current slice, what's committed, what's in flight, what's blocked.

**Push status: blocked, 61 commits unpushed** (as of the Wave 7 boundary, 2026-09-05; retried at this boundary per the once-per-wave policy, still 403 -- same credentials issue, user is fixing on their end). `git push origin feature/stock-intelligence-redesign` fails with a 403 (permission denied for the configured git credentials against `Anumulaashok/stock-test.git`) -- a credentials issue on the user's end, being fixed there, not fixable from this session. **Retry policy: once per wave boundary, not per slice** (per explicit instruction) -- so this count should only update at wave boundaries, not every commit. If a rate-limit gap ends this session before it's resolved, all commits below exist only on this machine -- check `git log --oneline origin/feature/stock-intelligence-redesign..HEAD` for the current unpushed count before assuming anything is on the remote.

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

## Wave 5 (in progress)

**Slice 1 — Alerts backend, done, committed (`ceb2250`).** Full-stack per D10: `AlertRow`/`AlertTriggerRow` (additive only), `AlertService` (user-scoped, follows `app/portfolio/service.py` exactly), `app/api/alerts.py`, registered in `app/main.py`. 5 condition types (price/score/DMA-crossover/regime-change), each reusing an already-existing cheap data source -- no new fetch infrastructure. Evaluates on read only; a condition's data being unavailable is its own status, never collapsed into "not met." 24 new tests, 1140/1140 backend tests pass.

**Screen-entry condition intentionally not implemented** -- no cheap persisted screening/ranking concept exists (`SectorRankingService` recomputes live via the full pipeline), which conflicts with "evaluate on read" being cheap. Logged as a design note, not a `BACKLOG.md` entry (it's not a missing endpoint, it's a scope call: the other 5 condition types are all O(1) reads, this one would be O(universe size) live recomputation).

**Slice 2 — Alerts frontend, done, not yet committed as of this line.** `/alerts` page (nav unlocked, moved out of `SideNav`'s `UPCOMING` list): create/toggle/remove alerts, auto-checks once on page open + manual "Check now" (D6 -- explicit copy states this is check-on-open, never continuous). Header bell (`TopBar`, replacing the old disabled placeholder) shows an unacknowledged-trigger count via a cheap DB-only read, separate from the expensive per-alert evaluate call -- verified by a test that the bell never fires `evaluateAlerts`. "Unavailable" (data couldn't be read) is visually distinct in wording from "not met," never collapsed together. 20 new tests. 322/322 frontend tests, `tsc -b`/`oxlint`/`vite build` clean. Eyeballed on new `/__dev/alerts` fixture route -- no issues found.

**Slice 3 — Comparison, done, not yet committed as of this line.** `/compare?tickers=A,B,C,D` (public, matches `/research`'s auth level -- comparing already-public research reports needs no login), reached via a new checkbox-select-then-"Compare selected" flow added to `WatchlistPage` (2-4 tickers, mirroring the pattern already used for research-run comparison in Wave 4). Aligned metric rows (Summary/Valuation/Financial metrics/Risk), never stacked detail pages. Best/worst emphasis restricted to rows with an already-established "higher is better" convention elsewhere in this app (overall score; a valuation method's own upside/downside %) -- explicitly NOT applied to the ~20+ raw financial metrics (ROE vs. debt/equity have opposite "better" directions, no per-metric directionality registry exists to draw on safely). "Unavailable" for a never-researched ticker or a missing metric, never blank/zero/borrowed from a neighboring column. 14 new tests. 338/338 frontend tests, `tsc -b`/`oxlint`/`vite build` clean. Eyeballed on new `/__dev/compare` fixture route -- confirmed the actual comparison logic reads each report independently (no cross-ticker contamination); the screenshot's identical ACME/BETA price and risk values were a fixture-construction oversight on this session's part, not a product bug.

**Slice 4 — Screener, done, not yet committed as of this line.** `/screener` (nav unlocked, public -- same level as `/research`/`/compare`, no login needed to view already-public research). Filters/sorts the up-to-100 most recently researched tickers via the existing `GET /recent` endpoint (URL-serialized filters, band multi-select, min-score threshold, 4 sort orders, CSV export, empty state naming the excluding filter). No virtualization added -- the 100-row backend cap makes it unnecessary at this scale; D12's list-virtualization allowance stays unused. 17 new tests. 355/355 frontend tests, `tsc -b`/`oxlint`/`vite build` clean. Eyeballed on new `/__dev/screener` fixture route (built by extracting a `ScreenerView` presentational component so the fixture drives the REAL component, not a rebuilt copy) -- band filter and empty state both confirmed correct.

**Sector/sub-score/fundamental filters and saved screens with a change feed: not built.** `/recent` (the only usable endpoint without new backend work) carries no sector/sub-score/fundamental data and is capped at 100 rows -- filed as 2 `BACKLOG.md` proposals rather than fabricating sector membership or sub-scores client-side.

**Not yet done in Wave 5:** Global News -- entirely unscoped this session (needs new backend aggregation across tickers with 30-minute-cache-respecting polling).

**Wave 5 is now functionally complete** for everything buildable without new backend authorization beyond D10 (Alerts full-stack, Comparison, Screener MVP). Global News and Screener's fuller feature set remain backend-gated, logged in `BACKLOG.md`.

---

**Wave 6, slice 1 — Contributors/detractors + position-size calculator, done, not yet committed as of this line.** `ContributorsDetractors` (sign-based buckets over `unrealized_gain_percent`, sort/select only, no new figure -- I2) and `PositionSizeCalculator` (I3's explicit carve-out: arithmetic over user input + a real quote, always Scenario-badged, no buy/sell/execute affordance, uses the backend's own `formatted_current_price` rather than reformatting the raw value client-side) both added to `PortfolioPage`. 11 new tests (6 pure-function + 5 for the two components), plus 4 pre-existing `PortfolioPage.test.tsx` assertions adapted for the correct new behavior (ACME now legitimately appears twice on a portfolio page with a positive-gain fixture holding -- HoldingsTable row + ContributorsDetractors row). 372/372 frontend tests, `tsc -b`/`oxlint`/`vite build` clean. Eyeballed on new `/__dev/portfolio-analytics` fixture route via Playwright, including a filled-in calculator (500000 account / 1% risk / entry 2500 / stop 2400 → 50 shares, ₹1,25,000 position value, ₹5,000 at risk -- correct).

**Everything else in Wave 6 requires new backend arithmetic or persistence and is not honestly buildable in the frontend:** portfolio value-over-time chart (no historical value snapshots exist), weighted score, sector concentration %, risk-band exposure %, XIRR, max drawdown, holdings correlation/overlap -- all logged as `BACKLOG.md` proposals. Wave 6 is functionally complete for what's buildable without new backend authorization.

---

**Wave 7, slice 1 — Empty states, layout-matching skeletons, ⌘K palette, done, not yet committed as of this line (see individual commits above this one).** Watchlist/Portfolio empty states now have a working one-click button that focuses the real add-form's input (verified via a Playwright click, not just a unit test asserting focus). `SkeletonWatchlistRows`/`SkeletonHoldingsTable` mirror their real component's actual shape instead of falling back to generic bare-line `SkeletonRows`. A global ⌘K/Ctrl+K command palette (`CommandPalette` + pure `parseCommand`) parses a bare ticker, `compare A B`, `screen score>N band:X`, or a known page name into an existing route, with a visible `⌘K` hint button in `TopBar` for discoverability -- an unsupported screener filter (sector, ROE) surfaces an honest inline error rather than silently being dropped, since neither is backed by a real endpoint. 393/397 frontend tests (the 4 failures are pre-existing, unrelated `AuthContext`/`WatchlistSummary` flakiness, confirmed identical on a clean stash of this session's changes), `tsc -b`/`oxlint`/`vite build` clean. Eyeballed via Playwright: both empty-state buttons actually move focus, both skeletons visibly match their real layout, and the palette opens/parses/navigates correctly including the sector-filter error case.

**Two Wave 7 items logged to `BACKLOG.md`, not built:** bulk-analyze queue with remaining-quota display (no real quota figure exists anywhere in the backend to read -- would be fabricated) and watchlist notes/tags/conviction (needs new `WatchlistItemRow` columns + a PATCH endpoint, genuine schema work, not yet D10-equivalent authorized).

**Wave 7, slice 2 — Sector heatmap and responsive nav, done.** `SectorHeatmap` toggles beside Discover's existing card grid: tiles colored by a real `sector_score` band (`sectorHeatBand`, a pure categorization of an existing value -- I2-safe), arrow-key traversable via a roving tabindex, a legend, and the score number always visible alongside color (G8). Verified against the real local backend via Playwright, not a fixture -- no sector reached the "strong" band in the live data and none was shown, confirming nothing is fabricated.

`SideNav` previously vanished entirely below its `lg:flex` breakpoint with **no replacement at all** -- a real gap, not a brief assumption mismatch. Now three synchronized layers share one `NavLinks` item list: the full labeled sidebar (`lg+`), an icon-only rail with title-attribute tooltips (`md`-`lg`), and a slide-in drawer below `md` (`MobileNavDrawer`, opened via a hamburger button in `TopBar`, same open-by-window-event pattern as `CommandPalette` so no state needed lifting through `AppShell`). Verified all three breakpoints via Playwright screenshots (1280px/900px/420px) plus the drawer's open state.

**Fundamentals' responsive item turned out to be a non-issue, not a gap:** checked the real `/stock/TCS/fundamentals` page at 375px via Playwright -- `FinancialSection`'s tables are only 3 columns (metric/value/status) and reflow cleanly with no horizontal overflow. The brief's "Fundamentals gets horizontal scroll with sticky metric column" wording assumes a wide multi-period table that doesn't exist in this app's real data model (one value per metric, not one column per period). Screener's own table (6 columns: ticker/company/score/band/date/status) already has `overflow-x-auto` from Wave 5. Nothing to fix here.

409/417 (all told, from this session's start) -- see individual test-file counts per slice above; the 4 recurring failures are pre-existing `AuthContext`/`WatchlistSummary` flakiness unrelated to any Wave 7 change (confirmed identical on a clean stash). `tsc -b`/`oxlint`/`vite build` clean throughout.

**Two more Wave 7 items logged to `BACKLOG.md`, not built:** "Ask Stock Agent" scoped to portfolio/screen/comparison (only one Q&A endpoint exists, `ask_ticker_question`, and it only accepts a ticker -- a scoped variant needs its own backend context-assembly and grounding citation, not a frontend reshape).

**Not attempted this session: restrained micro-interactions** (one hover treatment, one tab transition, one count-up) -- deliberately deferred rather than inventing ad hoc interaction choices without a clearer design reference; worth a dedicated pass once the rest of Wave 7/8 settles rather than bolting on incrementally.

**Wave 7 is now functionally complete for everything buildable without new backend authorization.** Two items remain backend-gated (bulk-analyze quota, watchlist notes/tags/conviction, Ask Stock Agent scoping -- 3 total across both slices), all in `BACKLOG.md`. Micro-interactions remain a deliberately deferred polish pass.

---

**Wave 8 — Light theme, done.** Per D8: one `:root[data-theme='light']` override block for the ~19 `--color-*`/`--chart-*` tokens (12 core palette + 7 status colors, plus 9 new `--chart-*` tokens introduced this wave for the two Chart.js components -- slightly more than D8's "~15" estimate since accessible-contrast status colors needed real darkening, not just a hue swap). `ThemeProvider`/`useTheme` set `data-theme` on `<html>` and persist the choice; dark stays the designed-for default, light is an explicit toggle (`ThemeToggle`, sun/moon, in `TopBar`), never a system-preference follow.

`PriceChart` and `AccuracyScatterChart` previously hardcoded every series/grid/tick/border color as a literal hex/rgba -- confirmed via `grep` that Chart.js was never actually reading any CSS variable despite D8's framing that it already did. Both now read colors through `chartTheme.readChartColors()` inside the effect that builds the chart, with `theme` added to that effect's dependency array so a theme switch triggers a real rebuild with fresh values (canvas isn't styled by CSS -- Chart.js never sees a `data-theme` change on its own). A few colors would have been outright broken on light without this: `AccuracyScatterChart`'s point border was `rgba(255,255,255,0.5)` (a white halo, invisible-to-backwards on white) and one border was hardcoded `#eef1fb` -- literally the dark theme's `--color-text` value, which would have blended into a light background instead of standing out.

**A real self-inflicted CSS bug caught before it shipped, not assumed fixed:** the first light-theme screenshot showed no visual change at all despite `data-theme="light"` correctly set on `<html>`. Traced it to the light override block's own doc comment containing a literal `--color-*/--chart-*` substring -- the `*/` inside that text prematurely closed the CSS comment, turning everything after it up to the next `*/` into raw (garbage) CSS, and corrupting the following `:root[data-theme='light']` selector into invalid `: root[...]` in the browser-parsed stylesheet (confirmed via `document.styleSheets` -- the light rule was completely absent from the parsed sheet, not just mis-applied). Fixed by rewording the comment to avoid embedding a `*/`-shaped substring; verified the fix by re-fetching the served CSS and re-screenshotting both a page and a chart in light mode.

**A real test-environment discovery, saved to memory for future sessions:** this project's vitest/jsdom `localStorage` global has no working `getItem`/`setItem`/`removeItem` at all (confirmed by direct probing -- every call throws `TypeError`). `ThemeContext`'s try/catch around persistence is load-bearing here, not defensive-code theater; `ThemeContext.test.tsx` stubs a real in-memory implementation via `vi.stubGlobal` to actually exercise the persistence path rather than only ever hitting its fallback branch.

420/424 frontend tests (the same 4 pre-existing `AuthContext`/`WatchlistSummary` failures, confirmed unrelated), `tsc -b`/`oxlint`/`vite build` clean. Verified via Playwright: light theme screenshotted on `/discover` (cards + heatmap), `/stock/TCS` overview (price+volume chart), and `/stock/TCS/forecast` (predicted line + confidence band) -- all legible with no color-on-color collisions; dark theme re-checked afterward to confirm no regression.

**Wave 8 is functionally complete.** This closes every wave in `docs/MASTER_BRIEF.md` §6 that was reachable without new backend authorization -- remaining backend-gated items across all waves are enumerated in `BACKLOG.md`.

---

**Wave 4 is now functionally complete** (research-run diff built; the other 3 asks correctly deferred to `BACKLOG.md` as genuine backend gaps; coverage-on-signal-card already existed from Wave 2). Continuing to Wave 5 next: Alerts backend is D10-authorized (additive tables, `app/portfolio/service.py` pattern, evaluate-on-read) -- starting there since it's clearly pre-approved, ahead of Screener/Comparison/News frontend work which hasn't been scoped this session.

---

**Wave 3 is now functionally complete** (deterministic section built first per sequencing instruction, then the ML section, never sharing a container -- I6/I7 held throughout).

---

**Wave 2 is now functionally complete** (D4 extraction, price chart + DMA/crossover/volume on Technical+Overview, resolved-prediction overlay, signal card). Regime bands, RS toggle, and the signal card's regime badge all correctly deferred, not fabricated. Score sparklines correctly unbuilt (D2/D11). Nothing in this wave committed yet beyond the earlier-pushed slice-1-fix commits.

## Blocked

Nothing yet. See `BLOCKED.md` (currently empty).

## Not started

Waves 3–8 in full, per `docs/MASTER_BRIEF.md` §6.
