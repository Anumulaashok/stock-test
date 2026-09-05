# Progress

Rewritten after every slice. Current wave, current slice, what's committed, what's in flight, what's blocked.

## Current wave

**Wave 1 — functionally complete, not yet committed for this turn's slice (health badge + CSV export).**

Operating mode: in-session, report-and-wait at wave boundaries, commit and push only on explicit user ask (per `docs/MASTER_BRIEF.md`'s own commit policy and the user's explicit choice on 2026-09-05 to run this way rather than the full unattended `docs/AUTONOMY.md` §3/§5 infrastructure).

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

## Built, awaiting commit instruction (this turn's slice)

**Wave 1.4 — data-source health badge.** Sidebar-footer badge, `DataSourceStatusContext` (single shared fetch, 5-min poll, pause-when-hidden, focus/visibility refetch), `SideNavHealthBadge`/`HealthBadgeView`, three-bucket classification (`healthy`/`degradedServing`/`actionRequired`) in `lib/dataSourceStatus.ts`, `DataSourcesPanel.tsx` refactored onto the shared context, dev fixture route `/__dev/health-badge` (8 states). See `DECISIONS.md` entries from 2026-09-05.

**Wave 1.6 — CSV export.** `lib/csv.ts` (`toCsv`/`downloadCsv`), `watchlistCsv.ts`, `portfolioCsv.ts`, export buttons wired into `WatchlistPage`/`PortfolioPage`.

**Wave 1.5 — Markdown export: dropped, not built.** See `BACKLOG.md`.

Verification floor as of this slice: 258/258 vitest, `tsc -b` clean, `oxlint` clean (no new warnings beyond the pre-existing pattern), `vite build` clean, both dev fixture routes (`/__dev/ml-panels`, `/__dev/health-badge`) confirmed absent from `dist/`.

## In flight

Nothing — Wave 1 is functionally done. Waiting on the user for: (a) commit/push instructions for the health-badge + CSV slice, (b) go-ahead to start Wave 2.

## Blocked

Nothing yet. See `BLOCKED.md` (currently empty).

## Not started

Waves 2–8 in full, per `docs/MASTER_BRIEF.md` §6.
