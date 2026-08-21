# stock-agent frontend

A presentation-only research terminal UI over the stock-agent backend
(Steps 1-9). It performs no financial calculation, valuation, scoring,
risk interpretation, or recommendation of any kind — it renders
whatever the backend's `InvestmentResearchReport` (Step 9) reports,
faithfully, including `unavailable`/`invalid`/`partial`/`failed` states.

## Stack

React + TypeScript + Vite + Tailwind CSS v4. No component library —
the surface area didn't justify one. No auth, no persistence, no
routing library (single page).

## Running

```bash
npm install
npm run dev
```

The dev server proxies `/api/*` to `http://127.0.0.1:8000` (see
`vite.config.ts`), so start the backend first:

```bash
cd .. && source .venv/bin/activate && uvicorn app.main:app --port 8000
```

Then open the printed local URL, enter a ticker (e.g. `AAPL`), and
click Analyze. Note the backend needs `FINANCIAL_DATA_API_KEY` (FMP)
configured to return real data — see the backend README.

## Testing

```bash
npm test
```

## Architecture

- `src/api/` — the only place that calls `fetch`. `client.ts` handles
  timeouts/errors generically; `analysis.ts` knows the one endpoint
  (`POST /api/v1/analyze/ticker`) this app calls.
- `src/types/backend.ts` — TypeScript mirrors of the backend's Pydantic
  models, derived from `model_json_schema()`, not guessed. Backend
  `Decimal` fields serialize as JSON strings, so numeric fields here are
  typed `string`.
- `src/lib/format.ts` — presentation-only formatting (parsing a decimal
  string for display, safe-URL checking). Never derives a new financial
  value; prefers the backend's own `formatted_*` fields where present.
- `src/components/` — one component per report section, each handling
  its own "unavailable" case so a missing section never crashes the
  page or hides the rest of the report.
- `src/pages/AnalysisPage.tsx` — the only stateful component (idle /
  loading / error / result), composes the section components in the
  priority order the product spec calls out for small screens.

## Known limitations

- No stage-by-stage progress during analysis — the backend doesn't
  expose one, and the loading state deliberately does not fabricate
  fake progress steps.
- No caching/persistence of past analyses — every search re-runs the
  full backend pipeline.
- Charts are not yet implemented (Step 10 phase 1 focused on the
  structured data views; see the final report for the recommended next
  phase).
