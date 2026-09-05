import numpy as np
import pandas as pd

from app.forecasting.ml.horizons import HORIZON_TRADING_DAYS, MlHorizon
from app.forecasting.ml.targets import build_targets, target_column


def _close_series(n: int = 300) -> pd.Series:
    dates = pd.bdate_range("2024-01-01", periods=n)
    values = 100 * (1.001 ** np.arange(n))
    return pd.Series(values, index=dates, name="close")


def test_target_is_return_not_price():
    close = _close_series(50)
    targets = build_targets(close)
    horizon = MlHorizon.D14
    days = HORIZON_TRADING_DAYS[horizon]
    col = target_column(horizon)
    expected = close.iloc[days] / close.iloc[0] - 1
    assert np.isclose(targets[col].iloc[0], expected)


def test_target_uses_trading_day_offset_not_calendar_days():
    close = _close_series(400)
    targets = build_targets(close)
    col = target_column(MlHorizon.M1)  # 21 trading sessions
    idx = 10
    expected = close.iloc[idx + 21] / close.iloc[idx] - 1
    assert np.isclose(targets[col].iloc[idx], expected)


def test_target_is_nan_past_end_of_series_never_fabricated():
    close = _close_series(30)
    targets = build_targets(close)
    col = target_column(MlHorizon.Y1)  # 252 sessions, series is only 30 long
    assert targets[col].isna().all()


def test_all_horizons_produce_a_column():
    close = _close_series(300)
    targets = build_targets(close)
    for horizon in MlHorizon:
        assert target_column(horizon) in targets.columns
