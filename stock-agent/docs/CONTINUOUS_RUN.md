# Continuous-Run Protocol

Companion to `docs/MASTER_BRIEF.md` (what to build) and `docs/AUTONOMY.md` (pre-decided answers, git policy). This document records the execution-mode change made on 2026-09-05: **full autonomous, never-pause-for-approval**, superseding the earlier in-session "report each wave and wait" mode.

## What changed and why

Earlier this session, asked how to execute the remaining waves, the user explicitly chose to stay in-session and report at each wave boundary before continuing. A later, much larger instruction set (asking for a fully trained ML forecasting system) explicitly demanded "never pause for approval," including on new dependencies and backend changes -- which directly conflicted both with that earlier choice and with `docs/AUTONOMY.md` D12 (dependency allowlist) and D14 (backend changes beyond D10 not authorized).

Rather than silently picking one, this was surfaced to the user as an explicit question. The user chose: **switch to full autonomous, never-pause mode**, following that brief's STEP 40-47 execution protocol. This document is that protocol, adapted to what actually runs here (an interactive session continuing turn-by-turn, not a separate supervisor process -- `docs/AUTONOMY.md` §3/§5's worktree/cron infrastructure was separately declined earlier and remains declined unless asked for again).

## Reconciling with prior explicit instructions

Two of the user's own earlier, specific instructions still apply and take precedence over the generic brief where they conflict:

- **Push cadence: once per wave boundary, not once per slice.** The user's own words: "retry push once per wave boundary rather than per slice so the log isn't full of the same failure." STEP 40's "attempt git push once" (per slice) is superseded by this for push *frequency*; each slice still gets committed, but push is only attempted at wave boundaries.
- **Commit granularity stays as established this session**: pre-existing code, features, policy guards/tests, and dev-only assets each get their own commit, by explicit path, never `git add -A`.

## What "never pause" actually means here

Proceed without stopping to ask, through:
- Implementation decisions within an approved wave or explicitly-requested feature.
- Test failures, provider unavailability, missing optional data, a single model's training failure, a dependency friction issue, or a blocked slice -- log it (`BLOCKED.md` if it's a genuine three-strike or hard-stop condition, `DECISIONS.md` for an ambiguity resolved conservatively, `BACKLOG.md` for a backend gap) and continue to the next independent slice.
- Wave boundaries -- advance immediately rather than reporting and waiting.

Still stop only for the hard stops in `docs/AUTONOMY.md` §6 (deleting/disabling existing functionality, auth/session/secret changes, a migration altering or dropping an existing column, an actual invariant conflict, a destructive git operation, or three consecutive failed attempts at the same slice).

## Per-slice checklist (STEP 40, adapted)

1. Run the ten self-review gates (`docs/MASTER_BRIEF.md` §4) explicitly.
2. Verify: `vitest`, `tsc -b`, `oxlint`, `vite build` (frontend slices); the project's pytest suite (backend/ML slices).
3. Confirm dev fixture routes stay excluded from `dist/`.
4. Actually look at degraded/empty states (G7) -- a fixture route or a direct test/DOM-dump check, not just "tests pass."
5. Commit by explicit path, never `git add -A`.
6. Do **not** attempt push here -- push is a wave-boundary action (see above).
7. Rewrite `PROGRESS.md`.

## Per-wave-boundary checklist (STEP 41, adapted)

1. Re-read `docs/MASTER_BRIEF.md` §2 (invariants).
2. `git diff main..HEAD` -- skim for anything that shouldn't be there.
3. Grep for `Math.random`, financial/statistical arithmetic in TypeScript (I2 risk), color-only encoding (G8 risk), inference chrome without a stated minimum n (G3 risk).
4. For every new visual: "what would a user conclude from this if they ignored its label?"
5. Attempt `git push` once. Log the result (success, or failure reason) in `PROGRESS.md`'s standing push-status line. Do not retry again until the next wave boundary.
6. Continue immediately to the next wave.

## Completion condition

Unchanged from the original brief's STEP 47: not "the frontend compiles," but every buildable item either committed or explicitly documented in `BLOCKED.md`. When that's true for all planned work, write a final `PROGRESS.md` and print exactly `ALL WAVES COMPLETE` -- never earlier.
