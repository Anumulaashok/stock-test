import numpy as np
import pandas as pd
import pytest

from app.forecasting.ml.features import build_price_features, build_relative_strength_features


def _ohlcv_frame(n: int = 260, start: float = 100.0, drift: float = 1.0005, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-01", periods=n)
    close = start * np.cumprod(drift + rng.normal(0, 0.01, n))
    high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    open_ = close * (1 + rng.normal(0, 0.002, n))
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates)


def test_sma200_is_nan_before_enough_history_never_fabricated():
    frame = _ohlcv_frame(150)
    features = build_price_features(frame)
    assert features["sma200"].isna().all()


def test_sma200_populates_once_enough_history_exists():
    frame = _ohlcv_frame(260)
    features = build_price_features(frame)
    assert features["sma200"].iloc[-1] == pytest.approx(frame["close"].iloc[-200:].mean(), rel=1e-9)


def test_feature_at_row_t_uses_only_data_up_to_t_no_lookahead():
    """Truncating the input frame at date T must not change any
    feature value computed for a date before T -- proof there is no
    forward-looking window anywhere in the pipeline."""
    frame = _ohlcv_frame(260)
    cutoff = 200
    full_features = build_price_features(frame)
    truncated_features = build_price_features(frame.iloc[:cutoff])

    common_index = truncated_features.index
    for column in truncated_features.columns:
        full_slice = full_features.loc[common_index, column]
        truncated_slice = truncated_features[column]
        pd.testing.assert_series_equal(full_slice, truncated_slice, check_names=False)


def test_relative_strength_features_align_on_shared_dates_only():
    stock = _ohlcv_frame(100)["close"]
    benchmark = _ohlcv_frame(100, seed=99)["close"].iloc[10:]  # shorter, offset history
    relative = build_relative_strength_features(stock, benchmark)
    assert relative.index.max() <= benchmark.index.max()
    assert relative.index.min() >= benchmark.index.min()


def test_rsi_bounded_between_zero_and_hundred():
    frame = _ohlcv_frame(260)
    features = build_price_features(frame)
    valid = features["rsi_14"].dropna()
    assert (valid >= 0).all() and (valid <= 100).all()
