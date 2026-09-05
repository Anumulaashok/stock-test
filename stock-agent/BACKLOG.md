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

## Not backlog — resolved

**Alerts backend** (originally Wave 4/5 backend request) is **authorized** under `docs/AUTONOMY.md` D10 (additive tables only, `app/portfolio/service.py` pattern, evaluate-on-read). This is Wave 5 build scope, not a backlog proposal.
