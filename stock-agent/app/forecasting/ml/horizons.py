"""Forecast horizons expressed in *trading sessions*, not calendar days.

`daily_price_history` and `ForecastingService`'s own `project_trading_date`
approximate trading days by skipping weekends only (documented limitation:
no NSE holiday calendar). The ML pipeline instead offsets by row position
in an actual observed trading-day price series, which gets holidays right
for free and matches what section 3 of the spec requires: "do not assume
calendar days when calculating historical outcomes."

Session counts below are the spec's own approximations (10/21/63/252
trading sessions for 14D/1M/3M/1Y).
"""

from enum import StrEnum


class MlHorizon(StrEnum):
    D14 = "14D"
    M1 = "1M"
    M3 = "3M"
    Y1 = "1Y"


HORIZON_TRADING_DAYS: dict[MlHorizon, int] = {
    MlHorizon.D14: 10,
    MlHorizon.M1: 21,
    MlHorizon.M3: 63,
    MlHorizon.Y1: 252,
}

ALL_HORIZONS: tuple[MlHorizon, ...] = tuple(MlHorizon)
