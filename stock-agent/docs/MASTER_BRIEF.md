# Stock Agent — Master Execution Brief

**Repo:** `stock-agent` · **Branch:** `feature/stock-intelligence-redesign`
**Frontend:** React + TS + Vite + Tailwind v4 (CSS custom properties on `:root`), Chart.js v4, Vitest, oxlint
**Backend:** FastAPI + async SQLAlchemy; deterministic math in Python; the LLM interprets, never computes

This supersedes Build Brief v1, v2, and the Wave 1 approval. It is self-contained: a fresh session can start from this document alone. It covers everything remaining, but it is **not** a licence to run start-to-finish unattended — §4 defines exactly where to stop.

---

## 1. Current state

**Landed:**
- `0df2f47` — StockLayout force-refresh computing fix + regression test
- `fea0491` — sidebar quote-card removal
- `chore(ml-forecast)` — pre-existing ML subsystem brought under version control unchanged
- `feat(ml-forecast)` — accuracy panel + prediction-vs-actual scatter (Wave 1 item 1)
- `test` — synthetic-data tripwire

**Built, pending fixture-route review and commit:**
- Wave 1 item 2 — news-impact and analogs panels

**Remaining in Wave 1:** dev fixture route, data-source health badge, Markdown export (endpoint unverified), CSV export.

**Everything from Wave 2 onward is unstarted.**

`RECON.md` at repo root holds the verified backend inventory: typed shapes for all five `/ml-forecast/*` endpoints, the research/snapshot endpoint family, provider chains and quotas. Read it before planning any wave.

---

## 2. Invariants — non-negotiable

Stop and report a conflict rather than resolving one yourself.

**I1 — No synthesized data.** No random walks, no gap interpolation, no dense series faked from sparse, no placeholder points. Missing data ships the empty state.

**I2 — Every number traces to a backend computation.** Never compute a displayed financial or statistical figure in TypeScript. Formatting and reshaping are yours; arithmetic and scoring are the backend's. Bucketing a list by a field it already carries is reshaping; deriving MAE from raw errors is not.

**I3 — No trade execution UI.** No Buy/Sell/Execute/Exit affordances, not even disabled. A position-size calculator is permitted — arithmetic over user input and a real quote.

**I4 — Descriptive register, never imperative.** "78/100 · Attractive" is a rating. "STRONG BUY" is advice. Applies to badges, tooltips, empty states, news cards.

**I5 — No market-depth / order-book UI.** No configured source.

**I6 — Forecasts are never blended, averaged, or reduced to one number.** Four independent deterministic methods; a separate parallel ML system. No cross-method averaging, no single "AI predicted price."

**I7 — The two forecasting systems never share a container implying equal validation.** Deterministic forecasting is documented as *not backtested*; ML tracks walk-forward accuracy. Separate sections, separate labelling, accuracy shown only where it exists.

**I8 — Chart type follows source provenance.** Only yfinance returns true OHLCV; others duplicate the daily close across all four fields. **No candlestick mode is built** (see D3). Line charts only.

**I9 — Statistics carry their sample size**, at equal visual weight, and inference chrome is suppressed below a stated minimum n.

**I10 — Model quality tier is always visible.** No-artifacts LOW quality and `data_available: false` must look distinct from a healthy result, not carry a quieter footnote.

**I11 — Scenario output is badged.** User-tuned inputs produce `SCENARIO`-badged output with the computed base case still on screen.

**I12 — No regressions.** Existing routes, tabs and toggles keep working. "Unavailable" states may be restyled, never hidden.

---

## 3. Standing decisions

**D1 — Lineage is stage-level, named "Run Inspector."** Snapshots store whole-blob JSON per stage with no per-metric provenance. Do not re-derive field-level lineage client-side (I2 risk). Exception: `ForecastSnapshotRow.metadata_json` carries genuine per-method provenance (reason, `r_squared`, status) and persists unavailable rows — the Forecast tab gets real granular lineage; don't flatten it to match weaker surfaces.

**D2 — Score sparklines and the score-efficacy lab are blocked**, not deferred for taste. `/research/ticker` reuses today's run, so a ticker gains at most one snapshot per day and only when analyzed. Score history is a function of usage; no backfill produces it. Prerequisite is a nightly universe re-analysis job that does not exist (§8).

**D3 — No candlesticks.** Chart.js needs the financial plugin, and I8 limits validity to one provider. Line + DMA overlays + volume sub-chart covers the need.

**D4 — `<PriceChart>` is an extraction from `ForecastLineChart`, at two real callers, in Wave 2.** Keep its gap-safe `null` alignment, instance teardown, and `role="img"` labelling. No second charting approach.

**D5 — `Datum<T>` is a rendering contract with per-endpoint adapters, not a universal wrapper.** ML responses carry richer availability semantics (`forecast_quality` + `quality_reasons`, `data_available` + `note`, `historical_accuracy: null`, `{sample_size: 0, note}`); adapters normalize for rendering while preserving those fields. The goal is that no call site can forget the empty case — not type uniformity.

**D6 — Alerts are full-stack and evaluate on read.** No scheduler exists. Follow `app/portfolio/service.py`: new tables, `user_id`-scoped service, router, async SQLAlchemy, pytest. The UI states plainly that alerts are checked when the app is open — never implies background monitoring or push.

**D7 — Sibling directories untouched.** `../reliance_ns_lstm_project/` and `../stock-agent-forecasting/` are unwired and superseded. If LSTM is ever wanted it enters as a model under `app/forecasting/ml/models/` under the same walk-forward contract, earning ensemble weight by inverse MAE — not as a parallel pipeline.

**D8 — Light theme is cheap.** Tokens are centralized `:root` custom properties in one CSS file; a light theme is a `[data-theme="light"]` override of ~15 properties. Still Wave 8. Chart.js reads CSS variables into canvas at construction, so charts need re-read on theme change.

---

## 4. Execution protocol

### Proceed without asking

Within an approved wave: implementing slices, writing tests, refactoring your own code from this session, extending fixtures, fixing what you broke.

### Stop and ask

- **Wave boundaries.** Every wave ends with a report and waits.
- **Any new dependency.**
- **Any backend change** — propose the shape, don't build it into the frontend.
- **Any invariant conflict.**
- **Deleting or rewriting existing code** you didn't write this session.
- **Anything that spends provider quota** — FMP 250/day, Finnhub 60/min, IndianAPI undocumented, Screener unofficial with a hand-managed cookie. Never trigger live research runs to check rendering; use the fixture route.
- **Touching shared layout** (`StockLayout.tsx`, `SideNav.tsx`, `StockHeader`) — its own PR, targeted edits only, `git diff --stat` before and after.

### Self-review gates — run before declaring any slice done

These encode real defects caught in review. Work them explicitly; don't assume.

- **G1 — Check the backend before disclosing a limitation.** If you're about to write a caveat about client-side truncation, filtering or bucketing, first read the relevant `app/` module to see whether a parameter already removes the problem. Eliminating beats documenting.
- **G2 — Guard scope.** Does a policy guard cover every directory where the risk actually lives? The tripwire missed `api/`, which is exactly where reshaping happens.
- **G3 — Inference minimum.** Any chrome implying a distribution (trend line, identity line, quadrant shading, band, percentile) is suppressed below a stated n. Never hide real data points — suppress the *inference*, not the observations.
- **G4 — Single authority.** When two visual channels encode one fact, name the backend field that wins and test the boundary case where they'd disagree. Decoration never overrules data.
- **G5 — No redundant fetches.** Check whether the data is already embedded in a response you hold. `MlForecastResult` embeds `news_impact`; each horizon embeds `analog`.
- **G6 — No premature abstraction.** Two real callers before extraction. A planned future caller is not a caller.
- **G7 — Degraded states get eyes, not just assertions.** Tests confirm text exists; only looking confirms legibility. Fixture route, every state, before done.
- **G8 — Color is never the sole channel.** Shape, fill, position or label carries it too.
- **G9 — Quota cost stated.** Any new fetch, poll or loop reports its call cost per user session before it ships.
- **G10 — Nothing computed in TS that the backend returns.** Grep your diff for arithmetic on financial or statistical values.

### Commit policy

Commit only when explicitly asked. Stage by explicit path; never `git add -A`. Separate commits for: pre-existing untracked code (unchanged, stated as such), features, policy guards and tests, dev-only assets. Imperative subjects. PR/commit body names the endpoint depended on and how it was verified.

### Verification floor, every slice

`vitest` green · `tsc -b` clean · `oxlint` clean · `vite build` succeeds · new states visible on the fixture route.

---

## 5. Remaining Wave 1

**1.3 — Dev fixture route.** `/__dev/ml-panels`, `import.meta.env.DEV`-guarded, no network, rendering every panel state side by side from the fixtures already in component tests: accuracy populated / n=3 / `sample_size: 0`; scatter all-correct / mixed / mostly-pending; news populated / `data_available: false` / recent event with no matching historical statistic; analogs `is_reliable` true and false, mean and median diverging. Judge legibility, not correctness — is the desaturated unreliable state still readable, do recent events and historical statistics read as different kinds of claim, does n=3 look intentional or broken, do markers separate at real size, does anything break at 375px. Keep out of the production bundle. Commit separately; this is a permanent asset that every later wave reuses.

**1.4 — Data-source health badge.** `GET /api/v1/market/data-sources/status` in the **sidebar footer** — global state, visible on every route, in the slot the quote card vacated. Not `StockHeader`, which is ticker-scoped. Compact, expanding to per-provider detail; `AUTH_EXPIRED` links straight to the Screener session-cookie control; FMP's 402-on-NSE/BSE reads as an expected limitation, not an outage.

**1.5 — Markdown export.** Verify `app/reporting/` is exposed over HTTP first. If not, drop from the wave and report — don't grow a backend task inside a frontend slice.

**1.6 — CSV export** for Watchlist and Portfolio. One shared `toCsv`: correct escaping, ISO dates, ticker/date in filename.

---

## 6. Waves 2–8

### Wave 2 — Charts and the signal card

- **`<PriceChart>` extraction** (D4) once Technical/Overview gives the second caller. Overlays as data, sub-chart slot, lazy-loaded, reduced-motion respected, keyboard-navigable.
- **Price chart on Technical and Overview**, line only. **Correction (found during Wave 2, logged in DECISIONS.md 2026-09-05): the claim below this line was wrong.** The Screener import's per-day DMA50/DMA200 series lands in `daily_price_history` (`DailyPriceHistoryRow.dma50`/`.dma200`) but is consumed only by `accuracy_service.py`'s evaluation step — it is never threaded through to `report.forecast`/`ReportHistoricalPricePoint`. What IS already on the report is `forecast.moving_averages`: a single **current-value** SMA50/SMA200 snapshot, not a per-day series. A true moving-DMA overlay requires new backend exposure — see `BACKLOG.md`, "Per-day DMA50/DMA200 series on the report." Until that lands, the honest version is a right-edge marker at the current SMA value (never a full-width line spanning history — see DECISIONS.md, "current-value-as-full-width-line"), which is what shipped in Wave 2 slice 1. **First check whether `report.forecast.historical_prices` (already passed into `MlForecastPanel`) is the same series**; if so, no new fetch (G5) — this part was correct and is what volume/close reuse today.
- **Golden Cross / Death Cross badge** driven by the crossover value already in the data model. Read it, don't recompute it (I2).
- **Volume sub-chart** on a shared axis. **RSI/MACD are not computed anywhere — do not build those panels.** Build the slot generically.
- **Regime bands** shaded from `regime.py`, with a legend.
- **Relative strength vs Nifty** as a toggleable series from the RS features already computed.
- **Resolved-prediction overlay** on the price chart — Wave 1's deferred secondary view, folded in here rather than built as a third chart.
- **Empty state** for missing history, pointing at Settings → System → Import Historical Data. Common real state; design it properly.
- **Signal card** atop stock detail: score gauge, band pill, top two positives and negatives, regime badge, provider/freshness badge, coverage indicator. Dense, terminal-like, computed-rating language.
- **Score sparklines: blocked** (D2). Do not build.

### Wave 3 — Forecast surfaces

Flagship wave. I6 and I7 throughout.

- **Deterministic section** — daily/weekly/monthly toggle reskinned into a multi-horizon card row (target date, projected value, % change, band), one row per method, parallel and never averaged, permanently labelled *not backtested*.
- **ML section** — separate, with ensemble output and per-model contributions from `ModelAgreementEntry`. Show weights as what they are: inverse walk-forward MAE. **Weight 0 means "no valid walk-forward result" and is genuinely informative — surface it, don't hide the model.** Quality tier badged (I10); the naive-only fallback looks unmistakably degraded.
- **Quantile bands** from `QuantileEstimate` (p10–p90), with `interval_coverage_80` from `/accuracy` shown alongside as the bands' own calibration.
- **Drivers** — `positive_drivers` / `negative_drivers` per horizon, as computed factors, not narrative.
- **Analogs and news-impact** already landed in Wave 1; integrate rather than duplicate.

### Wave 4 — Provenance

- **Run Inspector** (D1) — which `research_run_id` produced this view, when, which stage blobs exist with `created_at` and status. Stage-level everywhere; per-method granular on the Forecast tab.
- **Research run diff** — two dated runs side by side, changed fields highlighted. `/history` never recomputes, so this is cheap.
- **Score-change attribution** — delta decomposed by sub-score and driving metric ("Valuation −6: P/E 24.1 → 31.8 on price move, earnings unchanged"). Arithmetic over two snapshots; if that arithmetic must happen in TS, raise it as a backend request instead (I2).
- **Universe-relative percentiles** with cohort n, labelled as *tracked universe*, not sector — there is no peer/sector multiple source.
- **Coverage on the signal card** — a score from 6 of 11 inputs says so where the score is.

### Wave 5 — Screener, comparison, monitoring

- **Screener** (`/screener`, unlock nav): filter and sort the universe by score, sector, risk band, sub-scores, computed fundamentals. URL-serialized filters, virtualized past ~200 rows, column visibility, sticky header and first column, empty-result state naming the excluding filter, CSV export.
- **Saved screens with a change feed** — entries, exits, rank moves between runs. Server-persisted per D6's pattern.
- **Comparison** (`/compare?tickers=…`): 2–4 tickers as aligned metric rows with per-row best/worst emphasis — not stacked detail pages. Unavailable stays visibly unavailable per column; never blank, never zero, never borrowed from a sibling.
- **Alerts** (`/alerts`, unlock nav): full-stack per D6. Thresholds on score, price, DMA crossover, regime flip, screen entry. Header bell with unread count and `aria-live`. "Waiting for data" rather than silently never firing.
- **Global News** (`/news`, unlock nav): per-ticker news aggregated, with ticker chip, source, timestamp, filters (all / watchlist / sector / event type), countdown to refresh. **Poll no faster than the 30-minute server-side news cache** — a 5-minute client poll re-reads the same payload and burns quota (G9). Pause when hidden, show last success, degrade to manual refresh. Sentiment and event badges allowed; prescriptive calls and execute buttons are not.

### Wave 6 — Portfolio and risk

- **Portfolio performance chart** — value over time with Nifty/Sensex overlay, gated on real history.
- **Portfolio analytics** — weighted score, sector concentration, risk-band exposure, contributors and detractors, XIRR, max drawdown. Facts, not advice.
- **Position-size calculator** — account size, risk %, stop → share count from the real quote. `SCENARIO`-badged (I11). Not an order ticket (I3).
- **Correlation and overlap** from real price history, reporting the window used.
- **Score-efficacy lab: blocked** (D2). Note the distinction — the ML subsystem already tracks its own accuracy; this lab is about the *deterministic score*, which has no backtest.

### Wave 7 — Polish

Richer Watchlist/Portfolio empty states with a working one-click start · skeleton loaders matching real layout, ideally naming the running pipeline stage · ⌘K palette upgraded to commands (`compare TCS INFY`, `screen roe>20 sector:IT`) parsed into existing routes · sector heatmap on Discover as a toggle beside the card grid, keyboard-traversable, legend, no meaning by color alone · bulk analyze queue surfacing remaining quota before queuing · watchlist notes/tags/conviction, in CSV · Ask Stock Agent scoped to portfolio, screen or comparison, citing grounding metrics · responsive pass (sidebar to icons to drawer; Fundamentals gets horizontal scroll with sticky metric column — do **not** reflow dense financial tables into cards) · micro-interactions with restraint: one hover treatment, one tab transition, one count-up.

### Wave 8 — Light theme

Per D8. Verify chart series against the light ground; re-read CSS variables into Chart.js on theme change.

---

## 7. Design language

Near-black navy ground, indigo accent (~`#6366f1`), monospace for search/tickers/numerics, small-caps section labels with a leading accent bar, 1px-bordered cards, green/red deltas, pill badges, fixed sidebar, sticky search with Analyze.

Numerics monospace, tabular-figure, right-aligned in tables, consistent decimals per metric. Density is the aesthetic. Spend boldness in one place per screen. Quality floor, unannounced: visible focus, reduced motion, AA contrast on dark, no meaning by color alone.

The "AuraTrade Terminal" prototype is a visual reference only; its data is a seeded random walk. Borrow the layout language. Stock Agent's honest equivalents are stronger — a real event study instead of an invented impact figure, a real accuracy record instead of a confident tone.

---

## 8. Backend requests backlog

Raise as proposals with concrete shapes; do not implement inside frontend work.

1. **Per-stage source attribution** — one additive column per snapshot stage: `{ provider, via_fallback, source_status, fetched_at }`. The source manager already classifies this per fetch; it just isn't persisted. Unblocks a real Run Inspector (D1).
2. **Nightly universe re-analysis job** — prerequisite for score sparklines and the efficacy lab (D2). Proposal must include quota math (measure real per-ticker call counts first), staggering, failure handling.
3. **Alerts and saved-screens tables + service** (D6) — and, if alerts are ever to fire outside an open session, a scheduler, which is a separate architectural decision.
4. **Score-delta attribution endpoint**, if Wave 4's decomposition would otherwise require arithmetic in TypeScript.

---

## 9. When blocked

1. Data missing → build the honest empty state, log the gap, move on.
2. Data ambiguous → ask; don't assume it's real.
3. Brief conflicts with an invariant → stop, state it, propose the compliant alternative.
4. Shared layout involved → propose separately first.
5. A backend change would unlock a large frontend win → specify the endpoint shape and raise it, rather than reimplementing the computation in TypeScript.

---

**Next action: Wave 1 item 1.3, the fixture route. Report at the end of Wave 1 and wait.**
