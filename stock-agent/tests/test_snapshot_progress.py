"""`app.snapshot.progress` -- the in-memory, per-ticker stage tracker
that backs `GET /api/v1/research/{ticker}/progress`."""

from app.snapshot import progress


def test_a_fresh_run_starts_every_stage_pending():
    run = progress.start("ACME")
    assert [s.status for s in run.stages] == [progress.StageStatus.PENDING] * len(progress.STAGE_DEFINITIONS)
    assert run.finished is False
    assert run.research_run_id is None


def test_begin_complete_and_fail_transition_the_right_stage_only():
    run = progress.start("ACME")
    progress.begin_stage(run, "financials")
    progress.complete_stage(run, "financials", detail="ok")
    progress.begin_stage(run, "market")
    progress.fail_stage(run, "market", detail="unreachable")

    assert run.stage("financials").status == progress.StageStatus.SUCCESS
    assert run.stage("financials").detail == "ok"
    assert run.stage("market").status == progress.StageStatus.FAILED
    assert run.stage("market").detail == "unreachable"
    # Nothing else was touched.
    assert run.stage("analysis").status == progress.StageStatus.PENDING


def test_fail_stage_is_not_terminal_on_its_own():
    """A soft per-stage failure (e.g. financial fetch) must not mark the
    whole run finished -- only an explicit finish() call does."""
    run = progress.start("ACME")
    progress.fail_stage(run, "financials")
    assert run.finished is False


def test_finish_marks_the_run_finished_and_can_record_the_run_id():
    run = progress.start("ACME")
    progress.finish(run, research_run_id="run-123")
    assert run.finished is True
    assert run.research_run_id == "run-123"


def test_get_returns_the_most_recently_started_run_for_a_ticker():
    progress.start("DUPTEST")
    second = progress.start("DUPTEST")
    progress.finish(second, research_run_id="run-2")

    fetched = progress.get("duptest")  # case-insensitive lookup
    assert fetched is second
    assert fetched.research_run_id == "run-2"


def test_get_returns_none_for_an_unknown_ticker():
    assert progress.get("NEVERSTARTED-XYZ") is None
