"""Historical analog (nearest-neighbor) engine (spec section 7).

Given the current feature vector, finds historical rows (same ticker's
own history plus, when available, the pooled cross-ticker dataset --
see `app.forecasting.ml.pipeline`) whose feature vector was similar, and
reports what actually happened next. Distance is Euclidean over
z-score-normalized features (normalized using the *candidate pool's* own
mean/std, which is itself restricted to `date <= as_of` by the caller --
see the leakage note on `find_analogs`).

Only ever reports statistics when `sample_size` clears
`MIN_ANALOG_SAMPLE_SIZE` (spec: "Do not make recommendations based on
tiny samples").
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.forecasting.ml.horizons import HORIZON_TRADING_DAYS, MlHorizon
from app.forecasting.ml.targets import target_column

MIN_ANALOG_SAMPLE_SIZE = 20

ANALOG_FEATURE_COLUMNS = [
    "return_14d", "return_30d", "rsi_14", "price_vs_sma50", "price_vs_sma200",
    "volatility_20d", "volume_ratio_20d",
]


@dataclass(frozen=True)
class AnalogHorizonStats:
    horizon: MlHorizon
    sample_size: int
    positive_rate: float | None
    negative_rate: float | None
    mean_return: float | None
    median_return: float | None
    quantiles: dict[str, float] | None

    @property
    def is_reliable(self) -> bool:
        return self.sample_size >= MIN_ANALOG_SAMPLE_SIZE


@dataclass(frozen=True)
class AnalogResult:
    query_date: pd.Timestamp
    neighbor_count_requested: int
    horizon_stats: dict[MlHorizon, AnalogHorizonStats]
    neighbor_dates: list[pd.Timestamp]


def _normalize(pool: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    mean = pool[columns].mean()
    std = pool[columns].std().replace(0.0, np.nan)
    normalized = (pool[columns] - mean) / std
    return normalized, mean, std


def find_analogs(
    *,
    query_features: pd.Series,
    candidate_pool: pd.DataFrame,
    k: int = 60,
    feature_columns: list[str] | None = None,
) -> AnalogResult:
    """`candidate_pool` must already be restricted to `date <= as_of` by
    the caller (see `app.forecasting.ml.pipeline._historical_pool`) --
    this function performs no time filtering itself, so passing a pool
    that includes the future would leak it into the analog stats.

    `candidate_pool` must contain `feature_columns` plus one
    `target_return_<HORIZON>` column per `app.forecasting.ml.horizons.MlHorizon`
    (see `app.forecasting.ml.targets.build_targets`)."""
    columns = feature_columns or ANALOG_FEATURE_COLUMNS
    usable = candidate_pool.dropna(subset=columns)
    if usable.empty or query_features[columns].isna().any():
        empty_stats = {
            horizon: AnalogHorizonStats(horizon, 0, None, None, None, None, None)
            for horizon in HORIZON_TRADING_DAYS
        }
        return AnalogResult(
            query_date=pd.Timestamp(query_features.name) if query_features.name is not None else pd.NaT,
            neighbor_count_requested=k,
            horizon_stats=empty_stats,
            neighbor_dates=[],
        )

    normalized_pool, mean, std = _normalize(usable, columns)
    query_normalized = (query_features[columns] - mean) / std
    distances = np.sqrt(((normalized_pool - query_normalized) ** 2).sum(axis=1))
    neighbor_idx = distances.nsmallest(min(k, len(distances))).index
    neighbors = usable.loc[neighbor_idx]

    horizon_stats: dict[MlHorizon, AnalogHorizonStats] = {}
    for horizon in HORIZON_TRADING_DAYS:
        col = target_column(horizon)
        outcomes = neighbors[col].dropna() if col in neighbors.columns else pd.Series(dtype=float)
        n = len(outcomes)
        if n == 0:
            horizon_stats[horizon] = AnalogHorizonStats(horizon, 0, None, None, None, None, None)
            continue
        quantiles = {
            f"p{int(q * 100)}": float(outcomes.quantile(q)) for q in (0.10, 0.25, 0.50, 0.75, 0.90)
        }
        horizon_stats[horizon] = AnalogHorizonStats(
            horizon=horizon,
            sample_size=n,
            positive_rate=float((outcomes > 0).mean()),
            negative_rate=float((outcomes < 0).mean()),
            mean_return=float(outcomes.mean()),
            median_return=float(outcomes.median()),
            quantiles=quantiles,
        )

    return AnalogResult(
        query_date=pd.Timestamp(query_features.name) if query_features.name is not None else pd.NaT,
        neighbor_count_requested=k,
        horizon_stats=horizon_stats,
        neighbor_dates=list(neighbor_idx),
    )
