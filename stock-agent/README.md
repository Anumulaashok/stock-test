# stock-agent

An AI-assisted stock research and investment analysis system: give it a
ticker (or paste in financial statements directly) and it produces a
structured, evidence-backed research report — financial ratios,
valuation, a deterministic strength/risk score, a multi-horizon price
forecast, and an LLM-written narrative that interprets (never computes)
those numbers.

**Deterministic financial math always lives in plain Python**
(`app/financial/`, `app/valuation/`, `app/scoring/`, `app/forecasting/`)
— the LLM is never used to calculate a number, only to reason over
numbers that have already been calculated. This is the one rule every
layer below is built to preserve.

## Architecture

```
app/
├── api/            FastAPI routers (analyze, analyst, auth, portfolio, qa,
│                   research, search, sectors, health)
├── core/           Settings (env-based config) and logging setup
├── data/           Financial-statement providers (FMP, IndianAPI) behind a factory
├── market/         Market-data (quotes, price history) providers, same factory pattern
├── research/       News/market-context enrichment (Finnhub) — a data source, not
│                   to be confused with app/snapshot/'s "research run" below
├── cache/          SQL-backed response caching for the data/market layers
├── financial/      Deterministic ratio/metric calculations from raw statements
├── valuation/      DCF, comparable multiples, sensitivity analysis
├── scoring/        0-100 composite score + risk indicators
├── forecasting/    Deterministic daily/weekly/monthly forecasting (see below)
├── llm/            Provider-independent LLM abstraction (local/self-hosted, OpenAI-compatible)
├── analyst/        AI narrative interpretation over already-computed results
├── qa/             Follow-up Q&A assistant over the same deterministic context
├── pipeline/       Orchestrates financial -> valuation -> scoring -> forecast -> research -> analyst
├── application/    Wires ticker input -> data fetch (financial + market) -> pipeline;
│                   the one entry point both /analyze/ticker and the snapshot API use
├── snapshot/       Persists a whole analysis run as a dated, replayable "research
│                   run" (raw provider payloads, deterministic snapshots, forecast
│                   rows, cached LLM output) — see "Research snapshots" below
├── sectors/        Deterministic sector/market-opportunity ranking, averaged from
│                   the same per-ticker ScoringService output used everywhere else
├── reporting/      Turns a pipeline result into a presentation-ready report (+ Markdown export)
├── auth/           JWT authentication
├── portfolio/      Watchlist/portfolio persistence
├── search/         Ticker/company name autocomplete
└── db/             SQLAlchemy models (SQLite by default, Postgres in production)

frontend/           React + TypeScript SPA (Vite, Tailwind), dependency-free inline SVG charts
```

Every stage is injected into `AnalysisPipelineService`
(`app/pipeline/service.py`) as an interface, so each one can be faked in
tests. A stage failing degrades gracefully rather than taking down the
whole analysis: a deterministic stage (financial/valuation/scoring)
failing fails the pipeline; the AI analyst, research enrichment, and
forecasting are all optional — if any of them fails, the deterministic
results are still returned in full, with a warning attached.

`app/application/AnalysisApplicationService` sits one layer above the
pipeline: given just a ticker, it fetches `CompanyFinancials` (via
`app/data/`) and a market snapshot (via `app/market/`), then calls the
unmodified pipeline with the results. Both `POST /api/v1/analyze/ticker`
and the research-snapshot flow below call through this same service —
there is exactly one place that turns "a ticker" into pipeline input.

## Data providers, caching, and provider selection

Financial statements and market data come from pluggable providers
selected purely by an environment variable (`FINANCIAL_DATA_PROVIDER`,
`MARKET_DATA_PROVIDER`) — never hardcoded, and forecasting/reporting
code never imports a concrete provider directly. Currently supported:

- **Financial Modiling Prep (FMP)** — US-listed tickers.
- **IndianAPI** — NSE/BSE tickers. FMP's quote/historical-price
  endpoints require a paid plan for non-US symbols, so Indian tickers
  should use `indianapi` for both `FINANCIAL_DATA_PROVIDER` and
  `MARKET_DATA_PROVIDER`.
- **Finnhub** — news/research enrichment (opt-in per request).

Both financial-statement and market-data lookups are cached in the
app's own SQL database (`app/cache/`) — no separate cache
infrastructure. Financial statements change at most once a quarter, so
their default TTL is 7 days (`FINANCIAL_DATA_CACHE_TTL_SECONDS`); a
market quote is live data, so its default TTL is 30 seconds
(`MARKET_DATA_CACHE_TTL_SECONDS`). Forecasting reuses this same cached
market data — it never makes its own provider call.

## Financial analysis, valuation, and scoring

- **`app/financial/`** computes standard ratios (margins, growth,
  leverage, free cash flow, ...) from raw statements. Every metric
  carries a `status` (`calculated` / `unavailable` / `invalid`) and, if
  not `calculated`, a `reason` — nothing is silently defaulted to zero
  or dropped.
- **`app/valuation/`** — DCF (`app/valuation/dcf.py`), comparable
  multiples, and sensitivity analysis. DCF assumptions the caller
  doesn't supply (WACC, terminal growth rate) fall back to conservative
  defaults, but only ever with an explicit warning naming the value
  used — never silently.
- **`app/scoring/`** combines profitability, growth, financial health,
  cash flow, valuation, and risk into a single 0–100 score plus a
  green/yellow/red strength signal, renormalized over whichever
  categories actually have data. This is a data-quality/strength
  signal, not investment advice — it never says buy/sell/hold.

## Forecasting

`app/forecasting/` produces **four independent, never-blended**
deterministic projections. Nothing here is machine learning — every
number is a closed-form calculation over already-reported data, and
every method's `status`/`reason` is reported like any other metric in
this codebase.

1. **Statement CAGR extrapolation** — revenue, net income, EPS, and free
   cash flow projected forward from their historical compound annual
   growth rate: `future = base × (1 + CAGR)^year`.
2. **DCF bear/base/bull band** — the same `calculate_dcf` the valuation
   layer uses, reapplied at three FCF growth assumptions (±200bps
   around the base case). Never collapsed into one number.
3. **Price trend** — ordinary least squares linear regression over
   recent closing prices, extrapolated forward (floored at zero).
4. **Technical indicators** — 50-day/200-day simple moving averages,
   golden-cross/death-cross classification, 14-day rate-of-change
   momentum, and an SMA-crossover momentum drift.

### Daily / weekly / monthly horizons

The price-trend and technical projections are available at three
horizons, all built from the same underlying calculations — **weekly
and monthly never re-derive a new trend; they evaluate the exact same
fitted regression line at coarser trading-day offsets**:

| Horizon | Periods | Trading-day step | Label |
|---|---|---|---|
| Daily | 30 | 1 (every trading day) | "30 Trading Days" |
| Weekly | 12 | 5 (one calendar week) | "12 Weeks" |
| Monthly | 12 | 21 (≈ 252 trading days/year ÷ 12) | "12 Months" |

Only the price-trend line is a genuine per-period series — each of its
points is a real evaluation of the OLS fit. The moving-average,
crossover, and rate-of-change methods stay **single values at the
horizon's terminal period**, exactly as they always have: turning a
14-day rate-of-change into a fabricated week-by-week or month-by-month
path would invent math this codebase has no basis for. At non-daily
horizons, those methods' descriptions carry an explicit caution that a
short-term measurement is being applied across a much longer window.

DCF is never turned into a time series at any horizon — it is always
shown as a separate valuation reference (bear/base/bull), never merged
into the price-trend chart.

Forecast dates are trading-day-aware (weekends excluded) via
`project_trading_date`. Market holidays are **not** modeled: this app
serves both US and Indian tickers, and there is no single holiday
calendar correct for both, so a naive "skip Saturday/Sunday" projection
is the documented, honest approximation rather than a fabricated
exchange-specific calendar.

The API response (`ForecastResult` / the report's `ReportForecastSection`)
exposes `horizons.daily` / `.weekly` / `.monthly`, each with its own
price-trend series and technical-method breakdown, plus a
`historical_prices` field that echoes back the same closing-price
history the forecast was computed from (no second fetch) so a chart can
show the historical segment alongside the forecast segment. The
original single-horizon `price_trend_forecast` / `technical_forecast`
fields are kept for backward compatibility — they are literally
`horizons.daily`'s content, not a separate calculation.

**Nothing in this repository has been backtested.** These are
deterministic curve-fits over historical data, not validated
predictions — every forecast method carries a disclaimer to that
effect, and none of them should be read as a price target or investment
recommendation.

## AI analyst and Q&A assistant

`app/analyst/` sends the already-computed financial/valuation/scoring
(and optional research) results to an LLM and asks it to *interpret*
them — investment thesis, strengths/weaknesses, category-by-category
narrative. `app/qa/` lets a user ask a follow-up question against that
same deterministic context without a second full analysis run. In both
cases the LLM never calculates a number, never produces a forecast
value, and never fabricates a confidence score — it only writes
prose over numbers the deterministic layers already produced.

The LLM is accessed through a provider-independent interface
(`app/llm/base.py`); the only current implementation
(`app/llm/local_provider.py`) talks to a remote, OpenAI-compatible HTTP
endpoint (self-hosted or third-party), selected via `LLM_PROVIDER` —
never hardcoded.

## Research snapshots (persistent, dated, replayable runs)

`POST /api/v1/analyze/ticker` always computes fresh and never persists
anything. `POST /api/v1/research/ticker` (`app/api/research.py`,
`app/snapshot/service.py`) is the snapshot-aware alternative used by the
frontend's main analysis flow:

- A **normal** call reuses today's already-completed run for that
  ticker if one exists (no provider or LLM calls at all) — only the
  live quote is refreshed and spliced in, since price is cheap and
  stale within minutes while everything else isn't.
- `force_refresh: true` always computes a brand-new run and saves it
  **alongside** the old one — nothing already saved is ever
  overwritten, so history stays a genuine audit trail.
- Every stage's raw and derived output is captured as its own row:
  `RawResearchDataRow` (the raw provider payload — financial
  statements, market snapshot), `ResearchAnalysisSnapshotRow`
  (financial/valuation/scoring JSON), `ForecastSnapshotRow` (one row
  per forecast method per target date, across all three horizons),
  `LLMAnalysisSnapshotRow` (analyst output, keyed by a hash of its
  exact inputs so an unchanged input reuses a prior LLM response
  instead of re-asking the model), and `ResearchReportSnapshotRow` (the
  final assembled report). All hang off one `ResearchRunRow` per run.
- `GET /{ticker}`, `/{ticker}/history`, and
  `/{ticker}/history/{research_run_id}` only ever replay what was
  already saved — they never trigger computation, so browsing history
  is free. `/{ticker}/predictions` exposes the raw per-method forecast
  rows, laying the groundwork for a future backtesting pass
  (`PredictionOutcome` in `app/models/research_run.py` is defined but
  not yet populated by anything).
- Concurrency: a partial unique index on `(ticker, research_date)` for
  completed/partial runs makes two simultaneous normal requests for the
  same ticker+day race safely — the loser's insert fails, and it
  returns the winner's result instead of duplicating work.

The frontend surfaces this as `ResearchSnapshotBanner` ("Research
snapshot · Sep 2, 2026", with a manual refresh) and
`ResearchHistorySection` (a list of past runs, each re-openable without
recomputation) on the analysis page.

## Sector ranking

`app/sectors/` (`GET /api/v1/sectors` family) ranks a fixed universe of
sectors/tickers (`app/sectors/universe.py`) purely by averaging each
sector's constituents' existing `ScoringService.overall_score` — it
calls the same `AnalysisApplicationService` every other ticker flow
uses, in parallel across tickers, and adds nothing LLM-derived. An
optional news provider contributes only a headline count per sector,
never a score adjustment.

## Authentication, watchlist, and search

- **`app/auth/`** — JWT-based signup/login (`/api/v1/auth`).
- **`app/portfolio/`** — a per-user watchlist (`/api/v1/portfolio`).
- **`app/search/`** — ticker/company-name autocomplete
  (`/api/v1/search`), backed by the same financial-data provider
  factory as everything else.

## Frontend

React + TypeScript (Vite, Tailwind v4). Charts are dependency-free
inline SVG (`frontend/src/components/ForecastLineChart.tsx`) — no
charting library. The forecast UI (`ForecastSection.tsx`) exposes a
Daily/Weekly/Monthly horizon tab selector (defaulting to Daily); the
same chart component renders all three, fed different backend datasets
— it performs no calculation of its own. TypeScript types under
`frontend/src/types/backend.ts` are hand-mirrored from the backend's
Pydantic models; note that `Decimal` fields are serialized as JSON
*strings*, not numbers.

## Running the API

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in the providers/keys you want to use
uvicorn app.main:app --reload
```

Optionally start PostgreSQL via Docker Compose (the app runs on a local
SQLite file by default):

```bash
docker compose up -d db
```

### Key configuration

All configuration is environment-based (`app/core/config.py`); see
`.env.example` for the full, commented list. The main groups:

| Concern | Variables |
|---|---|
| LLM provider | `LLM_PROVIDER`, `LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL`, `LOCAL_LLM_API_KEY`, `LOCAL_LLM_*_TIMEOUT_SECONDS`, `LOCAL_LLM_ENABLE_THINKING`, `LOCAL_LLM_REASONING_*`, `LOCAL_LLM_JSON_MODE` |
| Financial data | `FINANCIAL_DATA_PROVIDER` (`fmp` \| `indianapi`), `FMP_*`, `INDIAN_API_*` |
| Market data | `MARKET_DATA_PROVIDER`, `MARKET_DATA_*_TIMEOUT_SECONDS`, `MARKET_DATA_RECENT_PRICES_LIMIT` (must stay ≥ 200 — the 200-day SMA/crossover forecast needs that much history) |
| Research | `RESEARCH_PROVIDER`, `RESEARCH_API_KEY`, `RESEARCH_*` |
| Caching | `FINANCIAL_DATA_CACHE_TTL_SECONDS` (default 7 days), `MARKET_DATA_CACHE_TTL_SECONDS` (default 30s) |
| Database | `DATABASE_URL` |
| Auth | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRES_MINUTES` |
| Response length | `ANALYST_MAX_RESPONSE_TOKENS`, `QA_MAX_RESPONSE_TOKENS` |

No IP addresses, model names, or credentials are hardcoded anywhere in
the codebase, and API keys are never included in logs, error messages,
or API responses.

### Endpoints

- `GET /health`, `GET /health/llm` — liveness/LLM connectivity checks.
- `POST /api/v1/analyze` — analyze caller-supplied financial statements.
- `POST /api/v1/analyze/ticker` — fetch statements by ticker, then
  analyze fresh, no persistence (opt into `include_price_trend_forecast`
  and `research.enabled` for the market-data-dependent sections).
- `POST /api/v1/research/ticker`, `GET /api/v1/research/{ticker}`,
  `/{ticker}/history`, `/{ticker}/history/{research_run_id}`,
  `/{ticker}/predictions` — the persistent, replayable snapshot flow
  (see "Research snapshots" above).
- `GET /api/v1/sectors/...` — deterministic sector ranking (see
  "Sector ranking" above).
- `/api/v1/auth`, `/api/v1/portfolio`, `/api/v1/qa`, `/api/v1/search`,
  `/api/v1/analyst` — see `app/api/`.

## Running tests

Backend:

```bash
pip install -r requirements.txt
pytest
```

All LLM/provider HTTP calls are mocked (via `respx`) — no live LLM
server or external API key is required to run the suite.

Frontend:

```bash
cd frontend
npm install
npx vitest run
npx tsc --noEmit
```

## What's implemented vs. not

Implemented: financial-statement ingestion (FMP, IndianAPI), market
data + response caching, deterministic financial analysis / valuation
(DCF, multiples) / scoring / risk signal, daily-weekly-monthly
forecasting, research enrichment (Finnhub), the AI analyst and Q&A
assistant, structured + Markdown reporting, persistent/replayable
research snapshots with LLM-response reuse, deterministic sector
ranking, JWT auth, a watchlist, ticker autocomplete search, and a full
React frontend.

Not implemented / explicitly out of scope for now: any machine-learning
or neural-network price prediction, forecast averaging into a single
"AI predicted price," fabricated confidence scores, peer/sector
multiple data (no data source exists for it, so target multiples are
never guessed), automatic target-price consensus, and historical
backtesting of the forecasting methods against realized outcomes.
