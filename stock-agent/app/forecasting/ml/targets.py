"""Forward-return target construction (spec section 4/15).

Targets are *returns*, not future prices (`future_close / current_close -
1`), and are computed via integer row-position offsets into the actual
observed trading-day series -- never a calendar-day shift -- so a target
for a 10-trading-day horizon is genuinely 10 real sessions ahead
regardless of holidays.

Leakage rule enforced here: `close.shift(-horizon_days)` only ever reads
rows *after* the current one; the last `horizon_days` rows of any series
necessarily get `NaN` targets (the future close doesn't exist yet) and
must be dropped from training, not filled.
"""

import pandas as pd

from app.forecasting.ml.horizons import HORIZON_TRADING_DAYS, MlHorizon


def build_targets(close: pd.Series) -> pd.DataFrame:
    """One column per horizon: `target_return_<HORIZON>` = close at
    `t + horizon_days` divided by close at `t`, minus 1. Index matches
    `close`. Rows where the future close falls outside the series are
    `NaN` (undecided outcome, not zero)."""
    out = pd.DataFrame(index=close.index)
    for horizon, days in HORIZON_TRADING_DAYS.items():
        future_close = close.shift(-days)
        out[f"target_return_{horizon.value}"] = future_close / close - 1
    return out


def target_column(horizon: MlHorizon) -> str:
    return f"target_return_{horizon.value}"
