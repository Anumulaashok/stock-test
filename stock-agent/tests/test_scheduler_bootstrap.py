"""`app.scheduler.scheduler` -- job registration only (never lets a real
job actually fire in a test process)."""

from app.core.config import Settings
from app.scheduler.scheduler import start_scheduler, stop_scheduler


def _settings(**overrides) -> Settings:
    defaults = dict(
        llm_provider="local", local_llm_base_url="http://test-llm:8080/v1", local_llm_model="test-model",
        database_url="postgresql+psycopg://user:pass@localhost/db",
    )
    defaults.update(overrides)
    return Settings(**defaults)


async def test_registers_market_open_and_close_jobs_at_the_right_ist_times():
    scheduler = start_scheduler(session_factory=object(), settings=_settings())
    try:
        jobs = {job.id: job for job in scheduler.get_jobs()}
        assert set(jobs) == {"research_refresh_market_open", "research_refresh_market_close"}

        open_trigger = jobs["research_refresh_market_open"].trigger
        assert str(open_trigger.timezone) == "Asia/Kolkata"
        assert {f.name: f for f in open_trigger.fields}["hour"].expressions[0].first == 9
        assert {f.name: f for f in open_trigger.fields}["minute"].expressions[0].first == 30

        close_trigger = jobs["research_refresh_market_close"].trigger
        assert {f.name: f for f in close_trigger.fields}["hour"].expressions[0].first == 15
        assert {f.name: f for f in close_trigger.fields}["minute"].expressions[0].first == 0
    finally:
        stop_scheduler(scheduler)


def test_disabled_flag_skips_starting_the_scheduler_entirely():
    scheduler = start_scheduler(session_factory=object(), settings=_settings(research_auto_refresh_enabled=False))
    assert scheduler is None


def test_stop_scheduler_tolerates_none():
    stop_scheduler(None)  # must not raise
