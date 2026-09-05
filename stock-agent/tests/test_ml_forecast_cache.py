from datetime import datetime, timedelta, timezone

from app.cache.store import CacheStore, CacheHit
from app.forecasting.ml.cache import CachedMlForecastPipeline


class _FakeCache(CacheStore):
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        if key not in self.store:
            return None
        now = datetime.now(timezone.utc)
        return CacheHit(value=self.store[key], cached_at=now, expires_at=now + timedelta(seconds=1800))

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


class _FakePipeline:
    def __init__(self) -> None:
        self.calls = 0

    async def predict(self, ticker: str, *, company_name=None):
        self.calls += 1
        from app.models.ml_forecast import (
            DataQuality,
            MlForecastResult,
            MlHorizonForecast,
            NewsImpactSection,
            QuantileEstimate,
            ForecastDriversResponse,
            AnalogSummary,
        )
        from app.forecasting.ml.horizons import ALL_HORIZONS

        horizon_forecast = lambda h: MlHorizonForecast(  # noqa: E731
            horizon=h.value, target_date="2026-01-01", current_price=100.0, expected_return=0.0,
            expected_price=100.0, quantiles=QuantileEstimate(), probability_positive=0.5,
            forecast_quality="LOW", quality_score=0.0, quality_reasons=[], model_agreement=0.0,
            model_outputs=[], drivers=ForecastDriversResponse(), analog=AnalogSummary(sample_size=0, is_reliable=False),
        )
        return MlForecastResult(
            ticker=ticker, generated_at="2026-01-01T00:00:00Z", data_date="2026-01-01", current_price=100.0,
            regime="UNKNOWN", horizons={h.value: horizon_forecast(h) for h in ALL_HORIZONS},
            news_impact=NewsImpactSection(), data_quality=DataQuality(
                price_history_days=0, fundamentals_available=False, news_available=False, regime="UNKNOWN",
            ),
            model_version="v1", feature_version="v1", news_model_version="v1", warnings=[],
        )


async def test_stale_cached_schema_is_treated_as_a_miss_not_a_500():
    cache = _FakeCache()
    inner = _FakePipeline()
    cached = CachedMlForecastPipeline(inner, cache)

    # Simulate a cache entry written by an older response schema (missing
    # the now-required `target_date`/`data_date` fields).
    stale_key = cached._key("TEST")  # noqa: SLF001
    await cache.set(stale_key, '{"ticker": "TEST", "current_price": 1.0}', 1800)

    result = await cached.predict("TEST")
    assert result.ticker == "TEST"
    assert inner.calls == 1  # fell through to a fresh computation instead of raising
