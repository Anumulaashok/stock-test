"""Deterministic market-regime classifier (spec section 6).

Rule-based today, but every rule reads only from the already-computed
feature row (see `app.forecasting.ml.features.build_price_features`), so
swapping this for a learned classifier later means changing
`classify_regime`'s body only -- callers (feature pipeline, analog
engine, explanation engine) consume `Regime` either way.

Deliberately not "golden cross = bullish": a golden cross combined with
high momentum *and* a large distance from SMA50 *and* elevated volatility
is flagged OVEREXTENDED, not TRENDING_UP, per spec section 6's own
example.
"""

from enum import StrEnum

import pandas as pd


class Regime(StrEnum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    OVEREXTENDED = "OVEREXTENDED"
    MEAN_REVERSION = "MEAN_REVERSION"
    BREAKOUT = "BREAKOUT"
    UNKNOWN = "UNKNOWN"


# Volatility above this (annualized) is "high" regardless of trend.
_HIGH_VOL_THRESHOLD = 0.40
# Distance from SMA50 beyond which an uptrend is "stretched."
_OVEREXTENDED_SMA50_DISTANCE = 0.15
_OVEREXTENDED_RSI = 75.0
_MEAN_REVERSION_RSI_LOW = 25.0
_MEAN_REVERSION_RSI_HIGH = 75.0
_SIDEWAYS_BAND = 0.03


def classify_regime(row: pd.Series) -> Regime:
    """`row` is one row of the merged feature frame (must contain
    price_vs_sma50, price_vs_sma200, sma50_vs_sma200, rsi_14,
    volatility_20d, breakout_flag, return_20d). Missing/NaN inputs
    (early in a series, before enough history exists) return UNKNOWN
    rather than guessing."""
    required = ("price_vs_sma50", "price_vs_sma200", "sma50_vs_sma200", "rsi_14", "volatility_20d", "return_20d")
    if any(pd.isna(row.get(col)) for col in required):
        return Regime.UNKNOWN

    price_vs_sma50 = row["price_vs_sma50"]
    price_vs_sma200 = row["price_vs_sma200"]
    sma50_vs_sma200 = row["sma50_vs_sma200"]
    rsi = row["rsi_14"]
    volatility = row["volatility_20d"]
    return_20d = row["return_20d"]
    breakout = bool(row.get("breakout_flag", 0.0))

    is_uptrend_structure = sma50_vs_sma200 > 0 and price_vs_sma200 > 0
    is_downtrend_structure = sma50_vs_sma200 < 0 and price_vs_sma200 < 0
    high_vol = volatility > _HIGH_VOL_THRESHOLD

    if breakout and return_20d > 0:
        return Regime.BREAKOUT

    if is_uptrend_structure and price_vs_sma50 > _OVEREXTENDED_SMA50_DISTANCE and (rsi > _OVEREXTENDED_RSI or high_vol):
        return Regime.OVEREXTENDED

    if rsi >= _MEAN_REVERSION_RSI_HIGH or rsi <= _MEAN_REVERSION_RSI_LOW:
        return Regime.MEAN_REVERSION

    if high_vol:
        return Regime.HIGH_VOLATILITY

    if is_uptrend_structure and return_20d > 0:
        return Regime.TRENDING_UP

    if is_downtrend_structure and return_20d < 0:
        return Regime.TRENDING_DOWN

    if abs(return_20d) < _SIDEWAYS_BAND:
        return Regime.SIDEWAYS

    return Regime.SIDEWAYS


def classify_regime_series(features: pd.DataFrame) -> pd.Series:
    return features.apply(classify_regime, axis=1)
