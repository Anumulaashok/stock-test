"""`build_source_registry` builds a fresh `SourceRegistry` per call (so
`configured` always reflects current settings/cookie state), but every
call must share one process-lifetime health store -- otherwise a
provider's observed health (`last_success_at`/`last_error_at`/`status`)
never accumulates, and `GET /api/v1/market/data-sources/status` always
reports empty health regardless of real traffic. See
`app.sources.registry.get_shared_health_store`.
"""

from app.sources.capabilities import Category
from app.sources.provenance import SourceStatus
from app.sources.registry import YFINANCE, SourceRegistry, get_shared_health_store


def test_health_recorded_on_one_registry_is_visible_on_a_later_one_via_shared_store():
    store = get_shared_health_store()
    first = SourceRegistry(
        chains={Category.MARKET_QUOTE: [YFINANCE]},
        configured={YFINANCE: True},
        health_store=store,
    )
    first.health(YFINANCE).record_success()

    second = SourceRegistry(
        chains={Category.MARKET_QUOTE: [YFINANCE]},
        configured={YFINANCE: True},
        health_store=store,
    )

    assert second.health(YFINANCE).status == SourceStatus.SUCCESS
    assert second.health(YFINANCE).last_success_at is not None


def test_health_resets_when_configuration_actually_changes():
    store = get_shared_health_store()
    configured = SourceRegistry(
        chains={Category.MARKET_QUOTE: [YFINANCE]},
        configured={YFINANCE: True},
        health_store=store,
    )
    configured.health(YFINANCE).record_failure(SourceStatus.UNREACHABLE, "timeout")
    assert configured.health(YFINANCE).status == SourceStatus.UNREACHABLE

    now_unconfigured = SourceRegistry(
        chains={Category.MARKET_QUOTE: [YFINANCE]},
        configured={YFINANCE: False},
        health_store=store,
    )

    assert now_unconfigured.health(YFINANCE).status == SourceStatus.NOT_CONFIGURED
    assert now_unconfigured.health(YFINANCE).last_error_at is None


def test_registries_without_a_shared_store_stay_isolated_from_each_other():
    """Existing direct `SourceRegistry(...)` construction (as used
    throughout the rest of the test suite) must keep its private,
    per-instance health -- this is what makes those tests deterministic
    regardless of what other tests observed."""
    first = SourceRegistry(chains={Category.MARKET_QUOTE: [YFINANCE]}, configured={YFINANCE: True})
    first.health(YFINANCE).record_success()

    second = SourceRegistry(chains={Category.MARKET_QUOTE: [YFINANCE]}, configured={YFINANCE: True})

    assert second.health(YFINANCE).last_success_at is None
    assert second.health(YFINANCE).status == SourceStatus.SUCCESS  # fresh-configured default, not observed
