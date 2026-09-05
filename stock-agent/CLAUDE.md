# stock-agent — Engineering Conventions

## Backend layering

Routers (`app/api/*.py`) are a thin transport layer only: parse the
request, call one service method, translate the result/exception to an
HTTP response. No business logic, no direct DB queries, no calls to an
external provider client in a router.

- **Controllers** — `app/api/*.py`. FastAPI routers. Own auth
  dependencies (`Depends(get_current_user)`), request validation via
  Pydantic models, and HTTP status/error mapping. Nothing else.
- **Services** — `app/<domain>/service.py` (e.g. `app/portfolio/service.py`,
  `app/forecasting/service.py`). Own the business logic and orchestration.
  A service method should be callable and testable with no FastAPI
  request/response objects anywhere near it.
- **Data access** — `app/db/models.py` (SQLAlchemy rows) plus the
  per-feature `*_service.py` helpers that read/write them (e.g.
  `app/data/daily_price_history_service.py`). External providers
  (Screener, yfinance, IndianAPI, FMP) live behind `app/sources/` /
  `app/market/providers/` / `app/data/providers/` adapters — a service
  depends on the adapter's interface, never on a specific provider's
  HTTP client directly.

Dependency injection: use FastAPI's `Depends()` for anything a route
needs (services, the DB session, settings, the current user) rather than
importing a global singleton. Follow `app/api/dependencies.py`'s
existing `build_*` factory pattern for constructing a service from
`Settings` + `AsyncSession` — add a new `build_x_service` there rather
than constructing services inline in a router.

## Error handling & logging

- A service raises a specific, named exception (e.g. `PortfolioError`,
  `ScreenerImportError`, `ResearchInProgressError`) — never a bare
  `Exception` or `ValueError` for a condition a caller needs to branch
  on. The router catches that specific exception and maps it to the
  right HTTP status; it never catches `Exception` broadly to paper over
  an unknown failure.
- Distinguish "this genuinely doesn't exist" (404 / `UNAVAILABLE`) from
  "the provider/service failed" (502/503 / `RATE_LIMITED`,
  `UNREACHABLE`, `AUTH_EXPIRED`) — see `app/sources/provenance.py`'s
  `SourceStatus` for the existing vocabulary. Don't collapse the two;
  a caller (and a fallback chain) needs to tell them apart.
- Log with `logger = logging.getLogger(__name__)` per module, structured
  as `event_name key=value key=value` (grep-able), e.g.
  `logger.warning("screener_lazy_mapping_write_failed ticker=%s", ticker, exc_info=True)`.
  Include `exc_info=True` on anything unexpected.
- A background/best-effort path (e.g. daily price accumulation after a
  research run) must never let its own failure break the caller's main
  result — catch, log, continue. A user-facing request path must not
  swallow an error that changes what the response means.
- Never fabricate a partial result to avoid an error. Returning `None`
  / an explicit "unavailable" status is correct when data genuinely
  isn't there; a guessed or interpolated value presented as real data
  is not (see `app/forecasting/ml/news/event_study.py`'s
  `compute_reaction` for the pattern: return `None` rather than a
  fabricated reaction).

## Naming conventions

- **Files**: `snake_case.py` (backend), `PascalCase.tsx` for React
  components, `camelCase.ts` for non-component TS modules (hooks,
  API clients, utils).
- **Python**: `snake_case` functions/variables, `PascalCase` classes,
  `UPPER_SNAKE_CASE` module-level constants. A DB row model is suffixed
  `Row` (e.g. `ScreenerCompanyMappingRow`); a Pydantic API/domain model
  is not (e.g. `PortfolioSummary`, `ForecastLineChartMarker`).
- **TypeScript**: `camelCase` functions/variables, `PascalCase`
  components/types/interfaces. A component's props type is inline or
  named `<ComponentName>Props` only when reused elsewhere — don't
  default to a named props type for a one-off component.
- Name for what a thing *is*, not the ticket/bug/PR that produced it —
  no `ticker2`, `newForecastPanel`, `fixedHelper`. If two things are
  genuinely similar, name the distinction (`historical` vs `predicted`,
  not `data` vs `data2`).
- A boolean is a predicate (`hasPrediction`, `isReliable`, `computing`),
  never a bare noun.

## Testing — what "done" means

A change isn't done until:
1. **Unit tests** cover the new/changed behavior at the service or
   pure-function level (not just an end-to-end happy path).
2. **Edge cases are explicit tests, not assumptions** — empty input,
   `None`/missing optional fields, a boundary value (0 rows, exactly
   the minimum sample size, the first/last element), and the failure
   path (provider error, insufficient data) each get their own test,
   the way `tests/test_screener_historical_lazy_mapping.py` covers both
   the exact-match and the ambiguous-no-match case.
3. **No N+1 queries** — a loop that hits the DB or an external
   provider once per item must become a batched query / bulk fetch
   before merge. If you're not sure, check for a `select(...)` or an
   `await client.get(...)` inside a `for`/list-comprehension over rows
   that came from an earlier query.
4. **Compiles clean**: `npx tsc --noEmit` (frontend) and the backend's
   test suite both pass before a PR is raised (see the pre-PR
   compilation check below — this is enforced, not optional).
5. A test that exercises a bug fix fails on the old code and passes on
   the new code — verify this, don't assume it.

## Algorithm / non-trivial logic proposals

Before implementing any non-trivial algorithm (a new ranking, matching,
scoring, forecasting, search, or optimization routine — not a simple
CRUD path), propose 2-3 candidate approaches first, each with:
- A one-line description of the approach.
- Time and space complexity.
- The concrete tradeoff that would make you pick it over the others
  here (data size, latency budget, accuracy vs. interpretability,
  how it degrades when an assumption breaks).

Only implement after that's discussed. Then write tests against edge
cases (empty/degenerate input, the smallest and largest realistic
input, an input that violates the algorithm's assumptions) *before*
considering the implementation complete — not as an afterthought pass.
Numbers over theory: when comparing approaches or claiming an
improvement, show the actual measured complexity/behavior, not a
qualitative guess.

## UI / frontend work

Follow the `frontend-design` skill's guidance for any new or
significantly reshaped UI: intentional typography and spacing, no
generic/templated AI-aesthetic defaults, a deliberate visual choice
over a Tailwind default. If a `DESIGN.md` exists at the repo root when
you do this work, check the change against its tokens (color, spacing,
type scale) before treating it as done; if it doesn't exist yet, don't
invent conflicting ad hoc values — stay consistent with the design
tokens already established in `frontend/src/index.css` / the existing
`var(--color-*)` custom properties.

## Branching & PRs

- Check `git branch --show-current` before starting work; continue on
  an existing feature branch with commits ahead of `main`, otherwise
  ask before creating a new one from `main`.
- Run the project's compile/build check before raising a PR; fix
  failures before opening it, never after.
