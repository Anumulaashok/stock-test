# Project Summary — stock-agent

Snapshot as of 2026-09-05, branch `feature/stock-intelligence-redesign`.
This file exists alongside `README.md` (the maintained, authoritative
doc) to capture **current branch state**, including work that
`README.md` doesn't reflect yet.

## What this is

An AI-assisted stock research and investment analysis system. Give it
a ticker and it produces a structured, evidence-backed report:
financial ratios, valuation (DCF + multiples), a deterministic
0–100 strength/risk score, a multi-horizon price forecast, and an
LLM-written narrative that *interprets* — never calculates — those
numbers.

**Core design rule:** deterministic financial math always lives in
plain Python (`app/financial/`, `app/valuation/`, `app/scoring/`,
`app/forecasting/`). The LLM is only ever used to reason over numbers
that have already been computed — it never produces a number itself.

## Stack

- **Backend:** Python, FastAPI, SQLAlchemy (async), SQLite by default
  / Postgres in production (Docker Compose), pandas/numpy for the ML
  forecasting layer, pytest + respx for tests (all external HTTP is
  mocked).
- **Frontend:** React + TypeScript, Vite, Tailwind v4, dependency-free
  inline SVG charts historically, now migrating the Forecast tab to
  Chart.js (see "Recent work" below). Vitest for tests.
- **LLM:** provider-independent interface (`app/llm/base.py`); the one
  implementation (`app/llm/local_provider.py`) talks to any
  OpenAI-compatible HTTP endpoint, selected via `LLM_PROVIDER` env var
  — never hardcoded to a vendor.
- **External data providers:** FMP, IndianAPI, yfinance, Screener.in,
  Finnhub, newsdata.io/newsapi.org — see the dedicated section below
  for exactly what each supplies, its cost/rate-limit tier, and how
  it's wired in.

## Data providers & external APIs — full detail

All providers are selected by env var (never hardcoded), sit behind a
factory (`app/data/factory.py`, `app/market/factory.py`), and are
never imported directly by downstream code — `app/financial/`,
`app/valuation/`, `app/forecasting/`, etc. only ever see the
provider-agnostic domain models. There are **two separate provider
axes** — financial *statements* and *market data* (quotes/history) —
because a provider that's good at one isn't necessarily good at the
other (e.g. FMP's statements work everywhere, but its market-data
endpoints are paywalled for non-US symbols).

### Financial statements — `FINANCIAL_DATA_PROVIDER` / `FINANCIAL_DATA_PROVIDERS`

| Provider | Coverage | Auth | Free tier | Notes |
|---|---|---|---|---|
| **FMP** (Financial Modeling Prep) | US-listed tickers | API key (`FMP_API_KEY`) | **250 requests/day** (as of 2026) — covers the annual income statement, balance sheet, and cash flow statement endpoints this app uses | `app/data/providers/fmp.py` / `fmp_client.py`, mapped via `app/data/mappers/fmp.py`. Base URL `financialmodelingprep.com/stable`. |
| **IndianAPI** (`stock.indianapi.in`) | NSE/BSE tickers | API key via `X-Api-Key` header (`INDIAN_API_KEY`) | Paid signup at indianapi.in — exact free-tier limits not documented in this repo's config, treat as unconfirmed | Name/search-based lookup, not a strict exchange-ticker match — `app/data/providers/indianapi.py` / `indianapi_client.py`, mapped via `app/data/mappers/indianapi.py` + `indianapi_historical.py`. |

Default priority chain: `FINANCIAL_DATA_PROVIDERS=indianapi,fmp` — the
source manager (`app/sources/manager.py`) tries IndianAPI first, falls
back to FMP on failure. Screener.in has **no** financial-statement
parser, so it's never eligible here even if listed.

### Market data (live quotes + price history) — `MARKET_DATA_PROVIDER` / `MARKET_DATA_PROVIDERS`

| Provider | Coverage | Auth | Cost | Notes |
|---|---|---|---|---|
| **yfinance** | US + Indian tickers | **None** — unofficial Yahoo Finance scraper | **Free**, no key, no documented rate limit (Yahoo can throttle/block at their discretion — an unofficial library, not a stable contract) | `app/market/providers/yfinance.py` / `yfinance_client.py`. The **only** one of the three that also supplies `market_cap`, `year_high`/`year_low`, and real per-day OHLCV (the others duplicate the daily close across OHLC). This is why it's the default (`MARKET_DATA_PROVIDER=yfinance`) and recommended for Indian tickers. |
| **FMP** | US-listed tickers only, effectively | Same `FMP_API_KEY` | Same 250 req/day tier as above | Returns **HTTP 402 for every NSE/BSE symbol** on the current plan — for Indian tickers it's inert as a market-data fallback (the call is attempted, fails cleanly, and the chain moves on). `GET /api/v1/market/data-sources/status` reports this outright so it's visible, not silent. |
| **IndianAPI** | NSE/BSE tickers | Same `INDIAN_API_KEY` | Same as above | Reuses the financial-statements key; no separate market-data key needed. |

Default priority chain: `MARKET_DATA_PROVIDERS=yfinance,fmp`.
`MARKET_DATA_RECENT_PRICES_LIMIT=210` — kept ≥200 because the 200-day
SMA/crossover forecast method needs that much trading history.
Quotes are cached for 30s (`MARKET_DATA_CACHE_TTL_SECONDS`); financial
statements for 7 days (`FINANCIAL_DATA_CACHE_TTL_SECONDS`) — both in
the app's own SQL cache table (`app/cache/`), no separate cache
infra (no Redis, etc.).

### Screener.in — the answer to "do we have a historical-data API"

**Yes** — but it is deliberately **not** a live `MarketDataProvider`
in the same sense as the three above. It's an **unofficial** API
(Screener publishes no public API/docs; `app/data/providers/screener_client.py`
hits the same JSON endpoints Screener's own website frontend calls)
used for **one specific purpose**: a manual, one-time historical
price **bulk-import backfill**, via
`POST /api/v1/market/{ticker}/historical/import`
(`app/data/screener_import_service.py`). It is also listed first in
`HISTORICAL_PRICE_PROVIDERS=screener,yfinance,fmp` and in
`COMPANY_SEARCH_PROVIDERS=screener,local` for company/ticker search.

Endpoints used (from `screener_client.py`):
- `GET /api/company/{company_id}/chart/?q=Price-DMA50-DMA200-Volume&days={days}&consolidated={true|false}`
  — historical daily price + 50/200-day moving average + volume series.
  Works **unauthenticated**.
- `GET /api/company/search/?q={query}&v=5&fts=1` — resolves a company
  name/ticker to Screener's internal numeric `company_id` and its
  canonical `/company/{TICKER}/...` URL (this is where the app derives
  the actual ticker symbol from — see `app/data/mappers/screener.py`).
  In practice **needs an authenticated session**
  (`SCREENER_SESSION_COOKIE`, set manually from a real browser's
  `sessionid` cookie — never committed, never logged).

Cost/limits: **no API key, free**, but also **no documented rate
limit or SLA** since it's unofficial — the client treats HTTP 429 as
rate-limited (honors `Retry-After`, capped at 5s), 401/403 as an
expired session cookie (falls back immediately, does not retry —
retrying a dead cookie only wastes time), 5xx as upstream-unavailable,
and retries transient failures up to `SCREENER_MAX_RETRIES`-equivalent
(`DEFAULT_MAX_RETRIES=2`) times with linear backoff. Because it's
scraping an unofficial endpoint, this is the most fragile provider in
the stack — expect it to need re-verification if Screener changes
their frontend.

### Research/news enrichment providers

| Provider | Purpose | Auth | Free tier | Notes |
|---|---|---|---|---|
| **Finnhub** | Company news for the AI-analyst "research enrichment" step (`RESEARCH_PROVIDER=finnhub`) | API key (`RESEARCH_API_KEY`) | **60 requests/minute** (as of 2026), no credit card required | `app/research/providers/finnhub.py` / `finnhub_client.py`. Opt-in per request (`research.enabled`) — the app runs fully without it. |
| **newsdata.io** | Sector news (Market Opportunity), Ask-AI grounding | API key (`NEWSDATA_API_KEY`) | Free tier exists (exact quota not documented here) | Optional — omitted entirely when unset. |
| **newsapi.org** | Same as above, alternate source | API key (`NEWSAPI_API_KEY`) | Free tier exists (exact quota not documented here) | Optional — omitted entirely when unset. |

News lookups are cached 30 minutes (`NEWS_CACHE_TTL_SECONDS=1800`).

### Provider fallback mechanics (`app/sources/manager.py`)

Every category (`FINANCIAL_DATA_PROVIDERS`, `MARKET_DATA_PROVIDERS`,
`HISTORICAL_PRICE_PROVIDERS`, `COMPANY_SEARCH_PROVIDERS`) is a
comma-separated priority chain, highest priority first. The manager
tries each provider in order and falls back on failure — a provider is
only ever tried for a category it actually implements (e.g. Screener
is skipped for `FINANCIAL_DATA_PROVIDERS` since it has no
statement parser, not silently treated as capable). Each provider
client classifies its own failures into a `SourceStatus`
(`AUTH_EXPIRED`, `RATE_LIMITED`, `UNREACHABLE`, `INVALID`, ...) so the
manager can decide "retry" vs. "fall back immediately" without
string-matching error messages. `GET /api/v1/market/data-sources/status`
surfaces live provider health (e.g. the FMP-402-for-NSE/BSE
limitation) so degraded providers are visible in the UI, not silent.

## Architecture (established, from `README.md`)

```
app/
├── api/            FastAPI routers — one per feature area
├── core/           Env-based settings + logging
├── data/           Financial-statement providers (FMP, IndianAPI) behind a factory
├── market/         Market-data (quotes/history) providers, same factory pattern
├── research/       News/market-context enrichment (Finnhub) — a data source
├── cache/          SQL-backed response caching for data/market layers
├── financial/      Deterministic ratio/metric calculations
├── valuation/       DCF, comparable multiples, sensitivity analysis
├── scoring/        0–100 composite score + risk indicators
├── forecasting/    Deterministic daily/weekly/monthly forecasting + (new) ML subsystem
├── llm/            Provider-independent LLM abstraction
├── analyst/        AI narrative interpretation over computed results
├── qa/             Follow-up Q&A assistant over the same context
├── pipeline/       Orchestrates financial → valuation → scoring → forecast → research → analyst
├── application/    ticker → data fetch → pipeline (single entry point)
├── snapshot/       Persists a whole analysis run as a dated, replayable "research run"
├── sectors/        Deterministic sector/market-opportunity ranking
├── reporting/      Pipeline result → presentation-ready report (+ Markdown export)
├── auth/           JWT authentication
├── portfolio/      Watchlist/portfolio persistence
├── search/         Ticker/company-name autocomplete
└── db/             SQLAlchemy models

frontend/           React + TypeScript SPA (Vite, Tailwind)
```

Every pipeline stage is injected as an interface
(`app/pipeline/service.py`), so a deterministic-stage failure fails
the whole analysis, but AI-analyst / research / forecasting failures
degrade gracefully — the deterministic results still return, with a
warning attached.

### Key flows

- **`POST /api/v1/analyze/ticker`** — fetch + analyze fresh, no
  persistence.
- **`POST /api/v1/research/ticker`** — the persistent, snapshot-aware
  flow the frontend actually uses. Reuses today's completed run per
  ticker unless `force_refresh: true`; every stage's raw and derived
  output is captured as its own DB row so history is a genuine,
  replayable audit trail. `GET /{ticker}/history` never recomputes.
- **`GET /api/v1/sectors/...`** — ranks a fixed sector/ticker universe
  purely by averaging existing per-ticker scores; no LLM involvement.
- **Deterministic forecasting** (`app/forecasting/`, non-ML) — four
  independent, never-blended projections (statement CAGR
  extrapolation, DCF bear/base/bull, OLS price-trend regression,
  technical indicators), each available at daily/weekly/monthly
  horizons. Explicitly documented as **not backtested** and not a
  price target.

## Recent / in-progress work on this branch

Git status shows substantial uncommitted work not yet reflected in
`README.md`:

### 1. New ML forecasting subsystem (`app/forecasting/ml/`, ~3,100 LOC)

A genuine machine-learning forecasting pipeline, separate from and
parallel to the existing deterministic forecasting — this **directly
supersedes** `README.md`'s current "Not implemented" line ("any
machine-learning or neural-network price prediction").

- **Models:** naive baseline, historical-mean-return, random forest,
  gradient-boosting quantile regression, and a historical-analog
  model (`app/forecasting/ml/models/`, `analog.py`).
- **Ensemble:** `app/forecasting/ml/ensemble.py` combines model
  outputs weighted by inverse walk-forward MAE (not arbitrary
  confidence) — a model with no valid walk-forward result gets weight
  0; if every model is weight-0, falls back to equal weighting rather
  than silently picking one model.
- **Features:** price-based features + relative-strength-vs-benchmark
  features (`features.py`), regime classification (bull/bear/choppy —
  `regime.py`).
- **News-driven signal:** a full sub-pipeline (`app/forecasting/ml/news/`)
  that classifies news events (type, sentiment, novelty, market
  timing), runs event-study analysis of historical price reactions per
  event type, and feeds that into the forecast.
- **Persistence & evaluation:** every prediction is persisted
  (`ForecastPredictionRow`) with `actual_return`/`actual_price` filled
  in later once the horizon elapses (`app/forecasting/ml/evaluation.py`),
  plus aggregated model performance by
  model/horizon/scope (`ForecastModelPerformanceRow`) — the
  backtesting/accuracy-tracking capability the deterministic forecaster
  explicitly lacks.
- **Training:** offline job (`app/forecasting/ml/training.py`) run via
  a CLI (`python -m app.forecasting.ml.backtest --train`), separate
  from the fast prediction-time pipeline (`pipeline.py`), which only
  ever loads pre-trained artifacts (`artifacts.py` / `ArtifactStore`)
  and never fits a model itself.
- **Degradation:** no trained artifacts → naive-only LOW-quality
  result with an explicit warning; no news client wired in →
  `news_impact.data_available=False`, not an error — same
  fail-soft philosophy as the rest of the codebase.
- **API:** new router `app/api/ml_forecast.py`, mounted in `app/main.py`,
  fully independent of the existing deterministic forecast endpoints:
  - `GET /api/v1/ml-forecast/{ticker}` — full multi-horizon forecast
  - `GET /api/v1/ml-forecast/{ticker}/history` — persisted past predictions
  - `GET /api/v1/ml-forecast/{ticker}/accuracy` — walk-forward/outcome performance
  - `GET /api/v1/ml-forecast/{ticker}/news-impact`
  - `GET /api/v1/ml-forecast/{ticker}/analogs`
- **New DB tables** (`app/db/models.py`): `ForecastPredictionRow`,
  `ForecastModelPerformanceRow`, `NewsEventRow` — additive, no
  migration risk to existing tables.
- **Test coverage:** 13 new test files under `tests/` covering the
  analog model, API, caching, ensemble quality, evaluation, event
  study, features, news classifier/timing, persistence, regime,
  targets, and validation.
- **Frontend surface:** `frontend/src/components/stock/MlForecastPanel.tsx`
  (231 lines) + `frontend/src/api/mlForecast.ts` +
  `frontend/src/types/mlForecast.ts` — a new panel, not yet
  necessarily wired into a route/tab (worth confirming before calling
  this "shipped").

### 2. Forecast tab chart migration (deterministic forecasting UI)

Per the latest commit (`f69f8cb`) and further uncommitted changes:
`ForecastLineChart.tsx` is being migrated from the dependency-free
inline-SVG charting `README.md` describes to Chart.js, with full
history + a 30-day prediction overlay. `StockLayout.tsx` and
`SideNav.tsx` also changed, suggesting the tab/nav structure is being
reshaped as part of the same "stock intelligence redesign" this
branch is named for.

### 3. Untracked sibling projects (outside this repo, same parent dir)

`../reliance_ns_lstm_project/` and `../stock-agent-forecasting/` are
untracked directories sitting next to this repo — likely exploratory
work related to the ML forecasting effort above, not part of this
repo's history. Worth checking with the user whether these should be
merged in, referenced, or left alone.

## What's implemented (stable, per README)

Financial-statement ingestion (FMP, IndianAPI), market data + caching,
deterministic financial analysis / valuation / scoring / risk signal,
daily-weekly-monthly deterministic forecasting, Finnhub research
enrichment, AI analyst + Q&A assistant, structured + Markdown
reporting, persistent/replayable research snapshots with LLM-response
reuse, deterministic sector ranking, JWT auth, watchlist, ticker
autocomplete, full React frontend.

## What's genuinely still missing

- Forecast averaging into a single "AI predicted price" (explicitly
  out of scope — the app always shows separate methods/bands).
- Peer/sector multiple data (no data source exists).
- Automatic target-price consensus.
- Backtesting of the **deterministic** forecasting methods (the new ML
  subsystem now has its own accuracy tracking, but that's separate).
- Confirmation that the new ML forecast panel/route is actually wired
  into the frontend navigation (exists as a component; wiring not
  verified in this pass).

## Where to look next

- `README.md` — full architecture reference, env var list, endpoint
  list, running/testing instructions. Should be updated once the ML
  forecasting work and Forecast-tab redesign land, since several of
  its claims (notably "no ML implemented") are now stale on this
  branch.
- `app/forecasting/ml/pipeline.py` — the ML prediction-time
  orchestrator; best single file to read to understand the new
  subsystem end-to-end.
- `app/forecasting/ml/backtest.py` — CLI entry point for training the
  ML models (`--train`).
