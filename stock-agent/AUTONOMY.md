# Autonomous Execution Contract

Companion to `docs/MASTER_BRIEF.md`. That document defines **what** to build and the invariants. This one defines **how to run without a human in the loop**: pre-decided answers, multi-agent topology, git policy, and rate-limit resumption.

Commit both to the repo before starting. Never paste either through chat — long documents truncate, and a truncated brief that claims authority over completed work is the worst possible input.

---

## 1. The autonomy contract

Human review is removed, not the reasoning it provided. It is replaced by three mechanisms:

1. **The ten self-review gates (§4 of the master brief) are now mandatory.** Work each one explicitly before declaring any slice done, and record the result. They are not a checklist to skim — every gate came from a defect that actually shipped past a first pass in this project.
2. **`DECISIONS.md`** — an append-only log at repo root. Every judgment call that would previously have been a question gets one entry: the ambiguity, the options, what was chosen, why, and what would reverse it. This is what the owner reads instead of answering questions in real time.
3. **`PROGRESS.md`** — current wave, current slice, what's committed, what's in flight, what's blocked. Rewritten after every slice. This is how a fresh session after a rate-limit gap resumes without re-reading the whole history.

**Ambiguity resolution rule:** when uncertain, choose the option that is more conservative with respect to the invariants — the one that shows less, claims less, and computes less in the frontend. Log it and continue. Never resolve ambiguity by building the more impressive version.

**Pressure warning.** An instruction to "build everything" creates pressure to produce something for every item on the list. Two items on that list are deliberately unbuildable right now (§2, D11). Producing a plausible-looking version of either is a worse outcome than leaving them undone, and the whole product premise is what makes that true.

---

## 2. Pre-decided answers

These replace every open question in the project history. Do not stop for any of them.

**D9 — Markdown export.** Check whether `app/reporting/` is exposed over HTTP. If yes, wire the button. If no, skip it, add a `BACKLOG.md` entry with the proposed endpoint shape, move on. Do not add a backend endpoint for this — it isn't worth the surface area unprompted.

**D10 — Alerts backend: authorized.** Build it per D6: new tables, `user_id`-scoped service module, router, async SQLAlchemy, pytest coverage, following `app/portfolio/service.py` exactly. Constraints: **additive tables only.** No migration that alters or drops an existing table or column. No changes to auth. Alerts evaluate on read; the UI says so plainly.

**D11 — Score sparklines and the score-efficacy lab: remain blocked. Do not build either.** They require score history that only accrues when a human runs an analysis, and the nightly re-analysis job that would produce it is not authorized here. Write the job proposal into `BACKLOG.md` — scope, quota math, staggering, failure handling — and move on. **Do not substitute a fabricated, sampled, or interpolated version. Do not draw a sparkline from two points.**

**D12 — Dependencies: one allowlist entry.** A list-virtualization library for the Screener (`@tanstack/react-virtual` or equivalent) *or* hand-rolled windowing, your choice. **Everything else is denied**, including any Chart.js plugin — no financial/candlestick plugin (D3), no annotation plugin (the existing custom-canvas-plugin technique already covers reference lines and shading).

**D13 — Provider quota: never spend it.** No live research runs to check rendering, ever. All visual verification happens on the fixture route against fixtures. The local `/market/data-sources/status` health endpoint is unmetered and may be polled.

**D14 — Backend changes beyond D10: not authorized.** Write the proposed shape to `BACKLOG.md` and build the frontend against the honest empty state. This covers per-stage source attribution, the score-delta attribution endpoint, and any scheduler.

**D15 — Sibling directories:** untouched (D7). No merging, referencing, or deleting.

**D16 — Uncommitted or untracked pre-existing code:** if any is found, commit it unchanged in its own commit, stated as pre-existing, before building on it. Never bundle it into a feature commit.

---

## 3. Multi-agent topology

Parallel agents editing one working tree corrupt each other. Use **git worktrees** — separate directories, separate branches, one integrator merging.

### Setup

```bash
BASE=feature/stock-intelligence-redesign
git worktree add ../sa-charts   -b wave/charts    $BASE
git worktree add ../sa-routes   -b wave/routes    $BASE
git worktree add ../sa-backend  -b wave/backend   $BASE
git worktree add ../sa-polish   -b wave/polish    $BASE
```

### Ownership — strictly disjoint

| Agent | Owns | Scope |
|---|---|---|
| **charts** | `components/charts/**`, `routes/stock/**` | Waves 2, 3 |
| **routes** | `routes/screener/**`, `routes/compare/**`, `routes/alerts/**`, `routes/news/**` | Wave 5 frontend |
| **backend** | `app/**`, `tests/**` | D10 alerts backend, backlog proposals |
| **polish** | `routes/portfolio/**`, `routes/watchlist/**`, `lib/csv.ts`, empty states | Waves 1 remainder, 6, 7 |

**Contested files — no agent edits these directly:** `SideNav.tsx`, `StockLayout.tsx`, `StockHeader`, the router registration file, `index.css`, and `components/ui/**`.

An agent needing a change to a contested file writes it to `INTEGRATION_REQUESTS.md` in its branch — the file, the exact change, the reason — and stubs around it. The integrator applies all requests in one pass per wave.

### Integration cadence

At each wave boundary, one integrator pass on the base branch:

1. Merge each wave branch in the order: backend → charts → routes → polish.
2. Apply all `INTEGRATION_REQUESTS.md` entries as one commit per contested file.
3. Run the full verification floor: `vitest`, `tsc -b`, `oxlint`, `vite build`.
4. Resolve conflicts toward the invariants; log any non-obvious resolution in `DECISIONS.md`.
5. Push, then reset each worktree branch onto the updated base before the next wave.

**Waves do not overlap across agents.** All four agents work the same wave, then integrate, then advance. Parallelism is within a wave, never across.

### If running a single agent instead

Ignore §3 entirely and work the waves sequentially on the base branch. Sequential is slower and strictly safer. The worktree setup is only worth its overhead if you're genuinely running four processes.

---

## 4. Git policy

- Work only on `feature/stock-intelligence-redesign` and its `wave/*` children. **Never commit to, merge to, or push `main`.**
- After every green slice: commit (explicit paths, never `git add -A`), then `git push origin <current-branch>`.
- **Never** `push --force`, `reset --hard`, `rebase` a pushed branch, `clean -fd`, or `checkout --` over uncommitted work.
- Commit granularity: features, policy guards/tests, dev-only assets, and pre-existing code each get their own commit.
- Every commit body names the endpoint depended on and how it was verified.
- Push after each commit rather than batching — a rate-limit stop mid-wave should never lose work.

---

## 5. Rate-limit resumption

**A rate-limited agent cannot schedule its own retry.** This must be an external process.

Save as `scripts/run-agent.sh`, `chmod +x`:

```bash
#!/usr/bin/env bash
set -uo pipefail

BRANCH="feature/stock-intelligence-redesign"
LOGDIR=".agent/logs"; mkdir -p "$LOGDIR"

seconds_until_0450() {
  local now target
  now=$(date +%s)
  if date -d "today 04:50" +%s >/dev/null 2>&1; then
    target=$(date -d "today 04:50" +%s)            # GNU
  else
    target=$(date -j -f "%Y-%m-%d %H:%M" "$(date +%F) 04:50" +%s)  # BSD/macOS
  fi
  (( target <= now )) && target=$(( target + 86400 ))
  echo $(( target - now ))
}

while true; do
  TS=$(date +%F-%H%M); LOG="$LOGDIR/run-$TS.log"
  echo "[$(date)] starting run" | tee -a "$LOG"

  claude -p "Read docs/MASTER_BRIEF.md and docs/AUTONOMY.md in full. \
Read PROGRESS.md and DECISIONS.md to resume. Continue from the current slice. \
Work autonomously per the autonomy contract. Commit and push after every green \
slice. Do not ask questions." >>"$LOG" 2>&1
  STATUS=$?

  if grep -qiE '429|rate.?limit|quota exceeded|overloaded' "$LOG"; then
    WAIT=$(seconds_until_0450)
    echo "[$(date)] rate limited; sleeping ${WAIT}s until 04:50" | tee -a "$LOG"
    sleep "$WAIT"
    continue
  fi

  if grep -q 'ALL WAVES COMPLETE' "$LOG"; then
    echo "[$(date)] done" | tee -a "$LOG"; break
  fi

  if (( STATUS != 0 )); then
    echo "[$(date)] exit $STATUS; retrying in 15m" | tee -a "$LOG"
    sleep 900; continue
  fi

  sleep 60
done
```

Run detached: `nohup ./scripts/run-agent.sh > .agent/supervisor.log 2>&1 &`

Notes:
- **Verify the CLI flags against `claude --help` before the first run.** Headless invocation and permission flags change between versions; the loop is the durable part, the invocation line is not. Non-interactive runs typically need a permission-mode flag — check what your version calls it.
- Add `.agent/` to `.gitignore`.
- For a persistent daily schedule instead of a supervisor loop, use cron: `50 4 * * * cd /path/to/repo && ./scripts/run-agent.sh`.
- `PROGRESS.md` is what makes resumption work. If it isn't current, a fresh session after a gap redoes or contradicts work. Rewrite it after every slice, not every wave.

---

## 6. Hard stops — halt and write to `BLOCKED.md`

Even under full autonomy, stop and leave a note rather than proceeding:

- Any change that would delete or disable existing user-facing functionality.
- Any change to authentication, session handling, or secret management.
- Any migration altering or dropping an existing table or column.
- Any situation where completing the task requires violating an invariant.
- Any destructive git operation.
- Three consecutive failed attempts at the same slice — stop, write what was tried and what failed, move to the next independent slice.

`BLOCKED.md` entries are the second thing the owner reads after `DECISIONS.md`.

---

## 7. Kickoff

```
Read docs/MASTER_BRIEF.md and docs/AUTONOMY.md in full before doing anything.

Work autonomously through the remaining waves. Do not ask questions — every
open decision is pre-answered in AUTONOMY.md §2. Resolve new ambiguity toward
the more conservative option and log it in DECISIONS.md.

After every slice: run the ten self-review gates, verify (vitest, tsc -b,
oxlint, vite build), check degraded states on the fixture route, commit by
explicit path, push, and rewrite PROGRESS.md.

At each wave boundary: integrate, verify, push, then advance.

Two items are deliberately unbuildable — score sparklines and the score-efficacy
lab. Write their backend proposals to BACKLOG.md and leave them undone. Do not
build a fabricated version of either.

When every buildable wave is complete, write a final summary to PROGRESS.md and
print the exact line: ALL WAVES COMPLETE
```

---

## 8. What to read when it finishes

`PROGRESS.md` (what got built) → `DECISIONS.md` (what it decided without you) → `BLOCKED.md` (what it refused) → `BACKLOG.md` (what needs backend work) → then `git log --oneline main..HEAD` and review the actual diffs on the surfaces that matter: anything rendering a number, and anything with an empty state.
