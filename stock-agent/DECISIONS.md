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
