# stock-agent

An AI-assisted stock research and investment analysis system, built
incrementally. This repository currently contains **Step 1: foundation
only** — no analysis, scoring, or agent logic is implemented yet.

## What this project is

The eventual goal is a system that analyzes a stock using company
fundamentals, financial statements, growth, profitability, cash flow,
valuation, management quality, competitive position, news/events, risk,
historical trends, and an AI-generated investment thesis.

Deterministic financial math will always be implemented in plain Python
(`financial/`, `valuation/`, `scoring/`) — the LLM is never used to
compute numbers, only to reason over already-computed facts.

## Current architecture (Step 1)

```
app/
├── api/         FastAPI routers (health checks only, for now)
├── core/        Settings (env-based config) and logging setup
├── llm/         Provider-independent LLM abstraction + local provider
├── models/      Pydantic domain models (Company, Stock, FinancialMetric, AnalysisRequest)
├── financial/   Placeholder — deterministic financial calculations (not implemented)
├── data/        Placeholder — data ingestion (not implemented)
├── valuation/   Placeholder — valuation models (not implemented)
├── scoring/     Placeholder — scoring logic (not implemented)
├── agents/      Placeholder — multi-agent orchestration (not implemented)
└── reports/     Placeholder — report generation (not implemented)
```

The LLM layer is built around an abstract `LLMProvider` interface
(`app/llm/base.py`) with a single concrete implementation,
`LocalLLMProvider` (`app/llm/local_provider.py`), which talks to a
remote, OpenAI-compatible HTTP API (e.g. a self-hosted Qwen model).
Application code depends on `LLMProvider`, obtained via
`app.llm.factory.get_llm_provider(settings)` — never on the concrete
class directly — so an OpenAI provider can be added later without
touching callers.

## Configuring the local LLM

Copy `.env.example` to `.env` and set:

```
LLM_PROVIDER=local
LOCAL_LLM_BASE_URL=http://YOUR_SERVER_HOST:PORT/v1
LOCAL_LLM_MODEL=your-model-name
LOCAL_LLM_API_KEY=            # optional, if your server requires one
LOCAL_LLM_TIMEOUT_SECONDS=30
```

`LOCAL_LLM_BASE_URL` must point to an OpenAI-compatible API root (i.e.
`{base_url}/chat/completions` and `{base_url}/models` must resolve).
No IP addresses, model names, or credentials are hardcoded anywhere in
the codebase.

## Running the API

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env with your local LLM server details
uvicorn app.main:app --reload
```

Endpoints:

- `GET /health` — process liveness check.
- `GET /health/llm` — attempts to reach the configured local LLM server
  and reports `ok`, `unreachable`, or `misconfigured`. Never returns
  secrets.

Optionally, start PostgreSQL via Docker Compose (not required to hold
real data yet):

```bash
docker compose up -d db
```

## Running tests

```bash
pip install -r requirements.txt
pytest
```

Tests mock all LLM HTTP calls (via `respx`) — no real LLM server is
required to run the unit test suite.

## What has NOT been implemented yet

- No financial calculations, valuation models, or scoring logic.
- No data ingestion (stock APIs, news APIs, web scraping).
- No vector database / retrieval.
- No multi-agent orchestration.
- No frontend.
- No OpenAI integration (interface is provider-independent so this can
  be added later).
- No authentication.
- No real PostgreSQL schema/data — the database is wired for
  configuration only.

## Planned future architecture

1. **Financial layer** — deterministic parsing and calculation of
   financial statement data in `financial/` and `valuation/`.
2. **Data layer** — ingestion from stock/news APIs into `data/`, backed
   by PostgreSQL via SQLAlchemy models.
3. **Scoring layer** — rules-based and/or model-assisted scoring in
   `scoring/`, consuming financial layer output (never raw LLM output)
   for numeric results.
4. **Agent layer** — orchestration in `agents/` that composes the
   financial, data, and scoring layers with the LLM abstraction to
   produce narrative analysis and an investment thesis.
5. **Additional LLM providers** — an OpenAI-backed `LLMProvider`
   implementation for more complex reasoning, selected via
   `LLM_PROVIDER` without changing any calling code.
6. **API expansion** — endpoints under `api/` exposing analysis
   requests/results once the above layers exist.
7. **Frontend** — a client for the API, once the API surface is stable.
