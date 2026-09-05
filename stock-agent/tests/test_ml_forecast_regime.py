import pandas as pd

from app.forecasting.ml.regime import Regime, classify_regime


def _row(**overrides) -> pd.Series:
    base = dict(
        price_vs_sma50=0.0, price_vs_sma200=0.0, sma50_vs_sma200=0.0,
        rsi_14=50.0, volatility_20d=0.15, return_20d=0.0, breakout_flag=0.0,
    )
    base.update(overrides)
    return pd.Series(base)


def test_missing_inputs_return_unknown_not_a_guess():
    row = pd.Series({"price_vs_sma50": None})
    assert classify_regime(row) == Regime.UNKNOWN


def test_plain_uptrend_structure_is_trending_up():
    row = _row(price_vs_sma50=0.03, price_vs_sma200=0.05, sma50_vs_sma200=0.02, return_20d=0.04, rsi_14=60)
    assert classify_regime(row) == Regime.TRENDING_UP


def test_golden_cross_with_stretched_price_and_high_vol_is_overextended_not_bullish():
    """Spec section 6: a golden cross plus high momentum plus a large
    distance from SMA50 plus elevated volatility must NOT be labeled a
    plain bullish trend."""
    row = _row(
        price_vs_sma50=0.20, price_vs_sma200=0.10, sma50_vs_sma200=0.03,
        rsi_14=80, volatility_20d=0.5, return_20d=0.15,
    )
    assert classify_regime(row) == Regime.OVEREXTENDED


def test_downtrend_structure_is_trending_down():
    row = _row(price_vs_sma50=-0.03, price_vs_sma200=-0.05, sma50_vs_sma200=-0.02, return_20d=-0.04, rsi_14=40)
    assert classify_regime(row) == Regime.TRENDING_DOWN


def test_flat_return_is_sideways():
    row = _row(return_20d=0.005)
    assert classify_regime(row) == Regime.SIDEWAYS


def test_extreme_rsi_is_mean_reversion():
    row = _row(rsi_14=82, return_20d=0.1, price_vs_sma50=0.02, price_vs_sma200=0.02, sma50_vs_sma200=0.01)
    assert classify_regime(row) == Regime.MEAN_REVERSION


def test_breakout_flag_with_positive_momentum_is_breakout():
    row = _row(breakout_flag=1.0, return_20d=0.06)
    assert classify_regime(row) == Regime.BREAKOUT
