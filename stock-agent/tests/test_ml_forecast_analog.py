import numpy as np
import pandas as pd

from app.forecasting.ml.analog import ANALOG_FEATURE_COLUMNS, MIN_ANALOG_SAMPLE_SIZE, find_analogs


def _pool(n: int, target_mean: float = 0.02, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = {col: rng.normal(0, 1, n) for col in ANALOG_FEATURE_COLUMNS}
    data["target_return_14D"] = rng.normal(target_mean, 0.05, n)
    return pd.DataFrame(data)


def test_small_sample_is_not_reliable():
    pool = _pool(MIN_ANALOG_SAMPLE_SIZE - 5)
    query = pool.iloc[0]
    result = find_analogs(query_features=query, candidate_pool=pool, k=60)
    stats = result.horizon_stats[list(result.horizon_stats)[0]]
    # sample_size is capped by pool size when pool < k
    assert stats.sample_size < MIN_ANALOG_SAMPLE_SIZE
    assert not stats.is_reliable


def test_large_sample_is_reliable_and_reports_stats():
    pool = _pool(500)
    query = pool.iloc[0]
    result = find_analogs(query_features=query, candidate_pool=pool, k=60)
    from app.forecasting.ml.horizons import MlHorizon

    stats = result.horizon_stats[MlHorizon.D14]
    assert stats.is_reliable
    assert stats.sample_size == 60
    assert stats.positive_rate is not None
    assert stats.quantiles is not None and set(stats.quantiles) == {"p10", "p25", "p50", "p75", "p90"}


def test_query_with_missing_features_returns_empty_not_fabricated():
    pool = _pool(500)
    query = pool.iloc[0].copy()
    query[ANALOG_FEATURE_COLUMNS[0]] = np.nan
    result = find_analogs(query_features=query, candidate_pool=pool, k=60)
    assert all(stats.sample_size == 0 for stats in result.horizon_stats.values())


def test_nearest_neighbors_are_actually_closer_than_average():
    """Sanity check the distance metric: neighbors of a query drawn from
    a distinct cluster should be closer in feature space than a random
    pool sample, not an arbitrary/random selection."""
    rng = np.random.default_rng(3)
    cluster_a = {col: rng.normal(0, 0.1, 200) for col in ANALOG_FEATURE_COLUMNS}
    cluster_b = {col: rng.normal(5, 0.1, 200) for col in ANALOG_FEATURE_COLUMNS}
    pool = pd.concat([pd.DataFrame(cluster_a), pd.DataFrame(cluster_b)], ignore_index=True)
    pool["target_return_14D"] = rng.normal(0, 0.05, 400)

    query = pd.Series({col: 0.0 for col in ANALOG_FEATURE_COLUMNS})
    result = find_analogs(query_features=query, candidate_pool=pool, k=50)
    # all 50 nearest neighbors should come from cluster_a (indices 0-199)
    assert all(idx < 200 for idx in result.neighbor_dates)
