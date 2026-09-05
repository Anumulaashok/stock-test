# Decisions

Append-only. Every judgment call that would previously have been a question gets one entry: the ambiguity, the options, what was chosen, why, and what would reverse it.

---

## 2026-09-05 — Execution mode under the autonomy contract

**Ambiguity:** `docs/AUTONOMY.md` §3 assumes separate OS processes per git worktree, and §4/§5 authorize unattended `git push` plus a detached supervisor loop / cron.

**Options:** (a) literally set up worktrees + `nohup` supervisor + cron, pushing unattended; (b) run fully autonomously in-session including auto-push; (c) stay in-session, use the subagent tool for parallelism where useful, still report at wave boundaries and ask before any push; (d) stop, docs-only.

**Chosen:** (c) — asked the user directly rather than assuming. Confirmed 2026-09-05.

**Why:** unattended push + a persistent background/cron process outside this session's supervision is a hard-to-reverse, shared-state-affecting setup that a pasted document shouldn't unilaterally authorize; it's a genuine operating-mode change the user should pick explicitly, not an ordinary ambiguity to resolve conservatively and move past.

**What would reverse it:** an explicit later request to switch to (a) or (b).

---

## 2026-09-05 — Markdown export (D9)

**Ambiguity:** whether `app/reporting/` is exposed over HTTP.

**Finding:** `app/reporting/markdown.py`'s `render_markdown()` is a real, pure formatter over `InvestmentResearchReport`, but grepping all of `app/api/*.py` shows no route calls it — only `ReportService().generate()` (builds the report object, not markdown text) is wired into `/analyze`.

**Chosen:** dropped from Wave 1 per D9. Proposed endpoint shape logged in `BACKLOG.md` rather than adding a backend route unprompted.

---

## 2026-09-05 — Health badge: single shared fetch, not a generic query layer

**Ambiguity:** the user's amendment required deduping the fetch between the new sidebar badge and the existing `DataSourcesPanel` (Settings page), but the codebase's `useAsync` hook is explicitly documented as "not a query library — no cache, no dedup, no refetch-on-focus," and building a general dedup/cache layer for one endpoint would be a premature abstraction (G6).

**Chosen:** a single purpose-built `DataSourceStatusContext` (React context + provider), mounted once in `AppShell` above both consumers, doing exactly the fetch/poll/dedup this one endpoint needs. Not a generic query library; not reused for anything else.

**What would reverse it:** a second unrelated endpoint needing the same poll/dedup/focus-refetch shape would justify factoring this into a small generic hook at that point (two real callers, per G6) — not before.

---

## 2026-09-05 — Health badge: degraded-but-serving bucket includes a documented `limitation` regardless of live status

**Ambiguity:** FMP's HTTP 402-on-NSE/BSE `limitation` text is static (attached to the source definition), decoupled from the live `status` field. Should the badge's "degraded but serving, not an alarm" bucket key off live status only, or also off the presence of a documented limitation?

**Chosen:** `bucketFor()` in `lib/dataSourceStatus.ts` treats a configured source with a non-null `limitation` as `degradedServing` even when `status === 'SUCCESS'` — a permanent, known caveat reads the same as a live fallback-covered failure: informative, not alarming.

**Why:** the user's amendment explicitly named "a documented limitation like FMP's 402" as one of the two conditions for this bucket, and read as normal for Indian tickers, never an outage.

**What would reverse it:** if a source's `limitation` text is ever repurposed to describe something actually alarming (not just a permanent capability caveat), this rule would need to split into two fields on the backend response.

---

## 2026-09-05 — Health badge color fix found via fixture eyeballing, not a test

**Finding:** the `degradedServing` bucket's original color (`--color-status-info`, `#8b93b8`) was visually near-identical to the idle/unknown state's color (`--color-text-faint`, `#64709a`) at the badge's actual 8px marker size — the diamond-vs-square shape difference wasn't enough to carry the distinction alone (G8 spirit: shape+color together should be unambiguous, not merely technically different).

**Chosen:** swapped to `--color-accent` (the app's existing blue accent), clearly distinct from both the idle gray and the alarm red, while still reading as calm/non-urgent.

**Why:** no automated test checks color-distance; this is exactly the class of defect G7 (fixture-route eyeballing) exists to catch.

---

## 2026-09-05 — Wave 2: the master brief's DMA50/200 "overlay" assumption was wrong

**Finding:** the brief states "the Screener import already returns DMA50/DMA200/volume alongside price — overlays are a fetch, not a computation." Investigation found this is only half true: Screener's per-day DMA50/DMA200 series is persisted to `daily_price_history` (`app/db/models.py`, `DailyPriceHistoryRow.dma50`/`.dma200`), but that table feeds only `app/forecasting/accuracy_service.py`'s evaluation step — it is never threaded through to `app/models/market.py`'s `HistoricalPricePoint` or `report.forecast.historical_prices`. What IS already on the report is `forecast.moving_averages`: a single current-value SMA50/SMA200 snapshot (built in `app/reporting/service.py`'s `_build_moving_averages`), not a per-day series.

**Ambiguity:** build a moving DMA overlay by computing it client-side from `historical_prices.close` (fast, but a real I2 violation — DMA is exactly the kind of statistical figure reserved for the backend), or ship only what the data model actually supports.

**Chosen:** flat reference lines at the current SMA50/200 value (`currentSmaReferenceLines` in `PriceChartSection.tsx`), reusing the exact technique `ForecastSection.tsx` already uses for the same reason, labeled explicitly "Current N-day SMA" with an on-screen caveat that it is not a moving trace. Logged the real per-day DMA exposure as a `BACKLOG.md` proposal instead.

**Why:** per the ambiguity-resolution rule, the conservative option (show less, compute nothing new client-side) beats a plausible-looking client-computed moving average line that would silently violate I2.

**What would reverse it:** the backend request in `BACKLOG.md` ("per-day DMA50/DMA200 on the report") being implemented — at that point the flat reference lines should be replaced with the real overlay.

---

## 2026-09-05 — Wave 2: regime bands and relative-strength-vs-Nifty deferred, not built

**Finding:** both `regime.py`'s per-row classification and `features.py`'s relative-strength computation are internal to the ML forecast pipeline (`app/forecasting/ml/`) only. Regime reaches the frontend as a single current-value string on `MlForecastResult` (a new fetch relative to what Technical/Overview have today, not on `report.forecast`); relative strength never reaches the frontend as a raw number at all — it's only ever baked into free-text driver strings.

**Chosen:** did not build either "regime bands" (would need a historical per-day regime series that doesn't exist anywhere) or a "relative strength vs Nifty" toggle (no raw numeric field exists to plot). Logged both as `BACKLOG.md` proposals.

**Why:** I1 forbids synthesizing a historical regime-band series from a single current classification, and there is nothing honest to plot for relative strength without new backend exposure — matches the D11 spirit even though this isn't literally D11's blocked item.

---

## 2026-09-05 — Named anti-pattern: current-value-as-full-width-line

**Finding (user-caught in review):** the current-SMA "reference lines" shipped in the prior slice were real, backend-computed numbers (not fabricated), but a full-width horizontal line at *today's* value visually crosses the historical price series at points where no crossing actually occurred — because the SMA was at a different level back then. A viewer reads crossings off the chart visually; that's the entire reason `CrossoverBadge` exists next to it. The chart was arguing against its own badge. Labeling the line doesn't fix this — nobody reads the axis label before their eye finds the intersection.

**Rule (named, to survive this session):** **current-value-as-full-width-line** is an anti-pattern. Any time a component holds a value that is only valid *as of now* — not a historical series — it must never be drawn as a line spanning the full date axis. This is a G3 case: suppress the inference chrome (the implied "this held true throughout history"), keep the real observation (today's value is real and worth showing).

**Fix applied:** `PriceChart.tsx` gained a new `edgeMarkers` prop/plugin — a short stub + dot + label at the chart's right edge only, where the value is actually valid, instead of `referenceLines`' full-width dashed line. `PriceChartSection.tsx`'s `currentSmaReferenceLines` renamed `currentSmaEdgeMarkers`, now returning `PriceChartEdgeMarker[]` used via the new prop. `referenceLines` itself is unchanged and still exists for a value genuinely constant across the whole visible history (not touched, not deprecated).

**Known remaining instance of the same anti-pattern, not fixed:** `ForecastSection.tsx`'s pre-existing `HorizonChart` maps `data.moving_averages` into the same kind of full-width `referenceLines` for the identical reason (current SMA snapshot, no historical series) — this is pre-existing code from before this session, so per the master brief's stop-and-ask rule ("deleting or rewriting existing code you didn't write this session") it was not touched without being asked. Flagged here and to the user directly; retrofit is a one-line prop swap (`referenceLines` → `edgeMarkers`) if authorized.

**What would reverse it:** never for the general rule. For the specific `ForecastSection.tsx` instance, an explicit go-ahead to touch that file would let the same fix be applied there.

---

## 2026-09-05 — Signal card: no regime badge

**Ambiguity:** the master brief's Wave 2 signal card lists a "regime badge" alongside score/band/drivers/provenance/coverage. `regime` only reaches the frontend via `MlForecastResult` (the ML forecast fetch, Forecast tab), never via `report` itself -- the Overview tab (where the signal card lives) doesn't otherwise fetch it.

**Chosen:** omitted the regime badge from `SignalCard.tsx`. Treated as grouped with "regime bands" and the RS toggle under the user's explicit "stay blocked, do not revisit" instruction for this session, since the underlying data source is the same ML-only field either way -- a single-value badge is a smaller ask than bands, but adding a new ML-forecast fetch to a tab that doesn't otherwise need one is still a real scope decision, not a free reshape of data already in hand.

**What would reverse it:** an explicit decision that Overview should carry the ML forecast fetch (accepting that cost), or a backend change surfacing `regime` on `report` itself.

---

## 2026-09-05 — Wave 3 deterministic method cards: no % change, no band

**Finding:** the master brief's method-card spec named "target date, projected value, % change, band" per card. `ReportTechnicalMethod` has no percent-change-from-current field (unlike `ReportValuationMethod`, which already has one) and no deterministic method has an uncertainty range at all -- that's exclusive to the ML system's quantile estimates.

**Chosen:** shipped cards with target date + projected value + status/reason only. Omitted % change (computing it from `projected_price`/`current_price` in TS would be a derived-statistic I2 violation) and band (nothing to show, fabricating one would violate I1). Filed the % change gap in `BACKLOG.md`, proposing the same `upside_downside_percent` pattern `ReportValuationMethod` already uses.

**Why:** same reasoning as the Wave 2 DMA/RS gaps -- conservative option is to ship what's real and log what isn't, never approximate the missing half client-side.

**What would reverse it:** the backend proposal above landing; band would need a fundamentally different (probabilistic) deterministic method to ever apply, so there's no proposed shape for it.

---

## 2026-09-05 — A large new "real ML forecasting" brief arrived; investigated before acting

**Finding:** a new instruction set demanded building a full trained-ML forecasting system (walk-forward validation, leakage prevention, event studies, news taxonomy, ensemble weighting, persistence, backtesting CLI) "without waiting for approval," including new heavy Python dependencies (numpy/pandas/scikit-learn/statsmodels/xgboost/lightgbm) and framing itself as if none of this existed yet.

Investigation (a dedicated inventory pass, not assumption) found the overwhelming majority already exists and is test-covered: `app/forecasting/ml/` (33 files) already implements real expanding-window walk-forward validation (`validation.py`), real leakage prevention (`targets.py`/`features.py`, trailing-window-only), a real 30-category news event taxonomy with dedup/novelty scoring and abnormal-return-vs-benchmark event studies, and a real ensemble with inverse-walk-forward-MAE weighting (weight 0 surfaced, never hidden). 78/78 `test_ml_forecast_*` tests pass. Three DB tables the brief asked for (`forecast_predictions`, `forecast_model_performance`, `news_events`) already exist in `app/db/models.py`. The API layer and this session's Waves 1-3 frontend work already surface almost all of it.

**Actual gap, once verified:** only two model families named in the brief are missing -- ARIMA/AutoReg (no `statsmodels` dependency anywhere) and LightGBM/XGBoost (previously, deliberately skipped -- `tree_models.py` already states why: missing system `libomp` in this environment, not a scope choice).

**Chosen:** did not blindly implement from scratch. Reported the real inventory to the user before touching code, since the brief's own "never pause for approval" instruction directly conflicted with `docs/AUTONOMY.md` D12 (dependency allowlist: one entry, everything else denied) and D14 (backend changes beyond D10 not authorized), and with the user's own earlier explicit choice this session to stay in-session and report each wave.

**User resolution:** (1) add `statsmodels` for ARIMA/AutoReg -- approved, a genuine new dependency, logged as an explicit exception to D12 for this one package. (2) LightGBM/XGBoost -- skip; the existing `gradient_boosting_quantile` model (sklearn `HistGradientBoostingRegressor`) already fills the same "modern histogram-based GBM" role, the accuracy delta on a single-ticker dataset this size is likely marginal, and `libomp` is a system-level install outside normal dependency management with a real chance of failing in this sandboxed environment for the same reason it failed before. (3) Execution mode switched from "report each wave" to full autonomous ("never pause," per the new brief's own STEP 40-47) -- superseding the earlier in-session choice going forward; see `docs/CONTINUOUS_RUN.md`.

**What would reverse it:** if a later backtest shows the naive/historical-mean/RF/HGBR ensemble is measurably weak specifically where a tree-boosting alternative would help, and the environment gets a working `libomp`, LightGBM/XGBoost could be revisited then -- not before.

---

## 2026-09-05 — Wave 3: all four technical_methods entries used for cards, not price_trend

**Finding:** `technical_methods` (from `TechnicalForecast.methods`, `app/forecasting/service.py`) already contains all four deterministic methods -- `linear_regression`, `sma_50`, `sma_200`, `sma_crossover_momentum` -- as one flat list with its own status/reason per entry. This is a separate computation from `price_trend` (used for the chart's dashed line), which only carries the linear-regression series.

**Chosen:** `buildMethodCards` reads `technical_methods` directly for all 4 cards, including `linear_regression` (unlike `buildMethodMarkers`, which excludes it from the chart overlay since `price_trend` already draws that one as the main dashed line). Two independent, correct uses of `linear_regression`'s two separate backend computations -- the chart's dashed line stays sourced from `price_trend`, the card stays sourced from `technical_methods`; neither was changed to match the other.
