# Progress

Rewritten after every slice. Current wave, current slice, what's committed, what's in flight, what's blocked.

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

**Not yet started in Wave 2:** Golden/Death Cross badge is done; still remaining — resolved-prediction overlay (Wave 1's deferred secondary view), the empty state is done, the signal card (score gauge/band pill/top drivers/regime badge/provider-freshness/coverage indicator). Regime bands and RS toggle are blocked pending the backend proposals above (not fabricating a version). Score sparklines remain correctly unbuilt (D2/D11).

## Blocked

Nothing yet. See `BLOCKED.md` (currently empty).

## Not started

Waves 3–8 in full, per `docs/MASTER_BRIEF.md` §6.
