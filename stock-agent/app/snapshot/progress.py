"""In-memory, best-effort progress reporting for an in-flight research
run -- the honest alternative to a fake staged loading animation.

`POST /api/v1/research/ticker` is (and stays) one blocking call; there is
no message queue or background worker in this single-process app to run
it asynchronously against. This module doesn't change that -- it lets
the SAME synchronous call report which of its own real, already-distinct
stages it is currently on, into a process-wide dict keyed by ticker, so
a concurrent `GET .../progress` request (polled by the frontend while
the POST is in flight) can show genuine stage-by-stage status instead of
an indeterminate spinner or, worse, an animated checklist with no data
behind it.

Deliberately in-memory and per-process, matching this app's existing
single-process assumptions (see `ResearchInProgressError`'s docstring)
-- progress is inherently ephemeral (meaningless after the run
finishes) and never persisted.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Stage:
    key: str
    label: str
    status: StageStatus = StageStatus.PENDING
    detail: str | None = None


# The real, already-distinct stages `ResearchSnapshotService.run_research`
# executes in order for a fresh (non-reused) run -- not a fabricated
# checklist; each one is an actual `await` boundary in that method.
STAGE_DEFINITIONS: list[tuple[str, str]] = [
    ("financials", "Fetching financial statements"),
    ("market", "Fetching market data"),
    ("analysis", "Running financial analysis, valuation & scoring"),
    ("analyst", "Generating AI analyst commentary"),
    ("report", "Generating report"),
    ("saving", "Saving results"),
]


@dataclass
class RunProgress:
    ticker: str
    research_run_id: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished: bool = False
    stages: list[Stage] = field(default_factory=lambda: [Stage(key=k, label=label) for k, label in STAGE_DEFINITIONS])

    def stage(self, key: str) -> Stage:
        for s in self.stages:
            if s.key == key:
                return s
        raise KeyError(key)


# Ticker -> its most recent run's progress. A ticker can only have one
# RUNNING research run at a time in practice (see the DB-level
# single-flight constraint on ResearchRunRow) -- overwritten, never
# appended, so this never grows unbounded across a long-running process.
_progress: dict[str, RunProgress] = {}


def start(ticker: str) -> RunProgress:
    ticker = ticker.strip().upper()
    progress = RunProgress(ticker=ticker)
    _progress[ticker] = progress
    return progress


def begin_stage(progress: RunProgress, key: str) -> None:
    progress.stage(key).status = StageStatus.RUNNING


def complete_stage(progress: RunProgress, key: str, *, detail: str | None = None) -> None:
    stage = progress.stage(key)
    stage.status = StageStatus.SUCCESS
    stage.detail = detail


def skip_stage(progress: RunProgress, key: str, *, detail: str | None = None) -> None:
    stage = progress.stage(key)
    stage.status = StageStatus.SKIPPED
    stage.detail = detail


def fail_stage(progress: RunProgress, key: str, *, detail: str | None = None) -> None:
    """Marks one stage failed -- not necessarily terminal for the whole
    run (e.g. a financial-fetch failure is soft; the pipeline continues
    on whatever it has). Callers that DO end the run on this failure
    call `finish()` themselves right after."""
    stage = progress.stage(key)
    stage.status = StageStatus.FAILED
    stage.detail = detail


def finish(progress: RunProgress, *, research_run_id: str | None = None) -> None:
    progress.finished = True
    if research_run_id is not None:
        progress.research_run_id = research_run_id


def get(ticker: str) -> RunProgress | None:
    return _progress.get(ticker.strip().upper())
