"""Technical + market-relative feature engineering (spec section 5/6).

Every feature at row `t` uses only `close[:t+1]` / `high[:t+1]` / etc --
trailing rolling windows and `.shift()` on the *raw* series, never a
centered or future-looking window. This is what makes the resulting
feature frame safe to slice at any historical date `T` and use to predict
`T+horizon` without leakage (spec section 15): a caller who does
`frame.loc[:T]` sees exactly the information a real trading-day-T
snapshot would have had.

Fundamentals are intentionally NOT joined here -- see
`app.forecasting.ml.pipeline` for the as-of join against
`CompanyFinancials`, which needs its own reporting-lag handling and
would leak if merged blindly on date.
"""

import numpy as np
import pandas as pd

_TRADING_DAYS_PER_YEAR = 252


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.where(avg_loss != 0, 100.0).fillna(50.0)


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    return macd, signal


def _stochastic_k(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    lowest = low.rolling(window, min_periods=window).min()
    highest = high.rolling(window, min_periods=window).max()
    rng = (highest - lowest).replace(0.0, np.nan)
    return ((close - lowest) / rng * 100).fillna(50.0)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return true_range.rolling(window, min_periods=window).mean()


def build_price_features(frame: pd.DataFrame) -> pd.DataFrame:
    """`frame` must have a sorted DatetimeIndex and columns
    open/high/low/close/volume (see `app.forecasting.ml.data`). Returns a
    new frame, same index, with one column per feature in spec section 5.
    Rows early in the series will have NaN for long-window features
    (e.g. SMA200 needs 200 prior rows) -- callers drop those rows before
    training/prediction rather than imputing them, per spec section 15
    ("never fabricate missing fundamentals" applies equally here: never
    fabricate missing technical history)."""
    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    volume = frame["volume"]
    out = pd.DataFrame(index=frame.index)

    for window in (1, 3, 5, 10, 14, 20, 30, 60, 90, 252):
        out[f"return_{window}d"] = close.pct_change(window)

    for window in (20, 50, 100, 200):
        out[f"sma{window}"] = close.rolling(window, min_periods=window).mean()
    for window in (20, 50, 200):
        out[f"ema{window}"] = close.ewm(span=window, adjust=False, min_periods=window).mean()

    out["price_vs_sma20"] = close / out["sma20"] - 1
    out["price_vs_sma50"] = close / out["sma50"] - 1
    out["price_vs_sma200"] = close / out["sma200"] - 1
    out["sma50_vs_sma200"] = out["sma50"] / out["sma200"] - 1

    out["rsi_14"] = _rsi(close, 14)
    macd, macd_signal = _macd(close)
    out["macd"] = macd
    out["macd_signal"] = macd_signal
    out["macd_hist"] = macd - macd_signal
    out["stochastic_k_14"] = _stochastic_k(high, low, close, 14)
    out["roc_14"] = close.pct_change(14) * 100

    daily_return = close.pct_change()
    out["atr_14"] = _atr(high, low, close, 14)
    out["volatility_20d"] = daily_return.rolling(20, min_periods=20).std() * np.sqrt(_TRADING_DAYS_PER_YEAR)
    out["volatility_60d"] = daily_return.rolling(60, min_periods=60).std() * np.sqrt(_TRADING_DAYS_PER_YEAR)
    out["volatility_change"] = out["volatility_20d"] / out["volatility_60d"] - 1
    out["high_low_range"] = (high - low) / close

    out["volume_sma_5"] = volume.rolling(5, min_periods=5).mean()
    out["volume_sma_20"] = volume.rolling(20, min_periods=20).mean()
    out["volume_ratio_5d"] = volume / out["volume_sma_5"].replace(0.0, np.nan)
    out["volume_ratio_20d"] = volume / out["volume_sma_20"].replace(0.0, np.nan)
    out["abnormal_volume"] = (out["volume_ratio_20d"] > 2.0).astype(float)
    out["volume_trend"] = out["volume_sma_5"] / out["volume_sma_20"].replace(0.0, np.nan) - 1

    rolling_high_252 = high.rolling(252, min_periods=20).max()
    rolling_low_252 = low.rolling(252, min_periods=20).min()
    out["distance_from_52w_high"] = close / rolling_high_252 - 1
    out["distance_from_52w_low"] = close / rolling_low_252 - 1
    running_max = close.cummax()
    out["recent_drawdown"] = close / running_max - 1
    out["breakout_flag"] = (close > rolling_high_252.shift(1)).astype(float)
    out["gap_pct"] = (frame["open"] - close.shift(1)) / close.shift(1)

    return out


def build_relative_strength_features(stock_close: pd.Series, benchmark_close: pd.Series) -> pd.DataFrame:
    """Aligns on date (inner join) and computes stock-vs-benchmark
    relative-strength features (spec section 5, "Market / sector").
    `benchmark_close` is typically NIFTY 50 (see
    `app.forecasting.ml.data.NIFTY_50_SYMBOL`); a sector benchmark can be
    passed the same way when sector index data is available."""
    aligned = pd.DataFrame({"stock": stock_close, "benchmark": benchmark_close}).dropna()
    out = pd.DataFrame(index=aligned.index)
    for window in (14, 30, 90):
        stock_ret = aligned["stock"].pct_change(window)
        bench_ret = aligned["benchmark"].pct_change(window)
        out[f"relative_strength_{window}d"] = stock_ret - bench_ret
    out["market_volatility_20d"] = aligned["benchmark"].pct_change().rolling(20, min_periods=20).std() * np.sqrt(
        _TRADING_DAYS_PER_YEAR
    )
    return out


FEATURE_COLUMNS: list[str] = [
    *[f"return_{w}d" for w in (1, 3, 5, 10, 14, 20, 30, 60, 90, 252)],
    "price_vs_sma20", "price_vs_sma50", "price_vs_sma200", "sma50_vs_sma200",
    "rsi_14", "macd", "macd_signal", "macd_hist", "stochastic_k_14", "roc_14",
    "atr_14", "volatility_20d", "volatility_60d", "volatility_change", "high_low_range",
    "volume_ratio_5d", "volume_ratio_20d", "abnormal_volume", "volume_trend",
    "distance_from_52w_high", "distance_from_52w_low", "recent_drawdown", "breakout_flag", "gap_pct",
]

RELATIVE_STRENGTH_COLUMNS: list[str] = [
    "relative_strength_14d", "relative_strength_30d", "relative_strength_90d", "market_volatility_20d",
]
