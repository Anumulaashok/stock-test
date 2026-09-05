# Progress

Rewritten after every slice. Current wave, current slice, what's committed, what's in flight, what's blocked.

**Push status: blocked, 24 commits unpushed** (as of the Wave 2 boundary, 2026-09-05). `git push origin feature/stock-intelligence-redesign` fails with a 403 (permission denied for the configured git credentials against `Anumulaashok/stock-test.git`) -- a credentials issue on the user's end, being fixed there, not fixable from this session. **Retry policy: once per wave boundary, not per slice** (per explicit instruction) -- so this count should only update at wave boundaries, not every commit. If a rate-limit gap ends this session before it's resolved, all commits below exist only on this machine -- check `git log --oneline origin/feature/stock-intelligence-redesign..HEAD` for the current unpushed count before assuming anything is on the remote.

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

**Not started:** the ML section (ensemble output, per-model contributions/weights, quality tier badging for the naive-only fallback, quantile bands + interval_coverage_80, drivers) -- next per the sequencing instruction. Analogs/news-impact already integrated in Wave 1, not duplicated.

---

**Wave 2 is now functionally complete** (D4 extraction, price chart + DMA/crossover/volume on Technical+Overview, resolved-prediction overlay, signal card). Regime bands, RS toggle, and the signal card's regime badge all correctly deferred, not fabricated. Score sparklines correctly unbuilt (D2/D11). Nothing in this wave committed yet beyond the earlier-pushed slice-1-fix commits.

## Blocked

Nothing yet. See `BLOCKED.md` (currently empty).

## Not started

Waves 3–8 in full, per `docs/MASTER_BRIEF.md` §6.
