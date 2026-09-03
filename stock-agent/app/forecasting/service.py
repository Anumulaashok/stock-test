"""Forecasting orchestration.

`ForecastingService` runs three independent, deterministic forecasting
techniques over already-computed pipeline data — it performs no I/O and
introduces no new calculation logic beyond what `calculations.py`
provides:

- Statement-level metrics (revenue, net income, FCF, EPS) extrapolated
  from their historical CAGR (`forecast_financials`).
- A bear/base/bull DCF valuation band built by reapplying
  `app/valuation/dcf.calculate_dcf` at different FCF growth assumptions
  (`forecast_valuation`) — never a new valuation method, never a single
  asserted target price.
- A naive linear-trend extrapolation of recent closing prices
  (`forecast_price_trend`), always carrying its disclaimer.

Each sub-forecast degrades independently: missing/insufficient input for
one never blocks the others, mirroring the pipeline's existing "a stage
can be partial" policy.
"""

from decimal import Decimal

from app.forecasting.calculations import (
    calculate_cagr,
    calculate_rate_of_change,
    calculate_sma,
    classify_moving_average_crossover,
    fit_linear_trend,
    project_metric,
    project_trading_date,
)
from app.models.financial_results import FinancialAnalysisResult, MetricStatus
from app.models.financial_statements import CompanyFinancials
from app.models.forecasting import (
    FinancialForecast,
    ForecastHorizon,
    ForecastResult,
    HorizonForecast,
    MovingAverageCrossover,
    MovingAverageResult,
    MultiHorizonForecast,
    PriceTrendForecast,
    PriceTrendPoint,
    TechnicalForecast,
    TechnicalForecastMethod,
    ValuationForecastRange,
    ValuationScenario,
)
from app.models.market import HistoricalPricePoint
from app.models.valuation import ValuationInput
from app.valuation.dcf import calculate_dcf

_SCENARIO_SPREAD = Decimal("0.02")  # +/- 200 bps around the base FCF growth assumption
DEFAULT_PROJECTION_YEARS = 5
DEFAULT_PROJECTION_DAYS = 30
SMA_SHORT_WINDOW = 50
SMA_LONG_WINDOW = 200
ROC_WINDOW = 14

_INCOME_STATEMENT_METRICS = [
    ("revenue", "USD"),
    ("net_income", "USD"),
    ("eps", "USD"),
]

# horizon -> (period count, trading days per period, human label).
# WEEKLY's 5 trading-days-per-week is exact absent holidays. MONTHLY's 21
# is the standard approximation (252 trading days/year / 12) -- there is
# no calendar-exact "trading days in a specific future month" without a
# holiday calendar this app doesn't have (see `project_trading_date`).
_HORIZON_SPECS: dict[ForecastHorizon, tuple[int, int, str]] = {
    ForecastHorizon.DAILY: (30, 1, "30 Trading Days"),
    ForecastHorizon.WEEKLY: (12, 5, "12 Weeks"),
    ForecastHorizon.MONTHLY: (12, 21, "12 Months"),
}

# Momentum-based methods (rate-of-change, SMA-crossover drift) measure a
# short window (ROC_WINDOW days, or the 50/200-day SMA spread) and apply
# it as a constant drift assumption. That's honest at the daily horizon
# it was designed for; stated without qualification at 12 weeks/months
# out it reads more confident than the underlying measurement supports.
_MOMENTUM_HORIZON_CAUTION = (
    " This measures a short-term pace and is applied unchanged across a much "
    "longer horizon -- treat it with more caution than the daily projection."
)


class ForecastingService:
    def forecast(
        self,
        *,
        company_financials: CompanyFinancials,
        financial_analysis: FinancialAnalysisResult,
        valuation_input: ValuationInput | None,
        recent_prices: list[HistoricalPricePoint] | None = None,
        ticker: str | None = None,
        projection_years: int = DEFAULT_PROJECTION_YEARS,
        projection_days: int = DEFAULT_PROJECTION_DAYS,
    ) -> ForecastResult:
        financial_forecast = self.forecast_financials(
            company_financials, financial_analysis, projection_years
        )
        valuation_forecast = (
            self.forecast_valuation(valuation_input, projection_years)
            if valuation_input is not None
            else None
        )
        resolved_ticker = ticker or company_financials.ticker or company_financials.company_name
        current_price = valuation_input.current_share_price if valuation_input else None
        price_trend_forecast = self.forecast_price_trend(
            resolved_ticker,
            recent_prices or [],
            projection_days,
        )
        technical_forecast = self.forecast_technical(
            resolved_ticker,
            recent_prices or [],
            current_price=current_price,
            projection_days=projection_days,
        )
        horizons = self._build_multi_horizon_forecast(
            resolved_ticker, recent_prices or [], current_price, price_trend_forecast, technical_forecast
        )
        historical_prices = sorted(
            (p for p in (recent_prices or []) if p.close is not None),
            key=lambda p: p.timestamp,
        )

        # sma_50/sma_200-unavailability warnings depend only on price
        # history depth, not horizon -- daily/weekly/monthly would
        # otherwise repeat the identical string three times.
        technical_warnings = (
            technical_forecast.warnings + horizons.weekly.technical.warnings + horizons.monthly.technical.warnings
        )
        warnings: list[str] = []
        warnings.extend(financial_forecast.warnings)
        if valuation_forecast:
            warnings.extend(valuation_forecast.warnings)
        warnings.extend(dict.fromkeys(technical_warnings))

        return ForecastResult(
            company=company_financials.company_name,
            financial_forecast=financial_forecast,
            valuation_forecast=valuation_forecast,
            price_trend_forecast=price_trend_forecast,
            technical_forecast=technical_forecast,
            horizons=horizons,
            historical_prices=historical_prices,
            warnings=warnings,
        )

    # --- Statement-level forecasting --------------------------------------------------

    def forecast_financials(
        self,
        company_financials: CompanyFinancials,
        financial_analysis: FinancialAnalysisResult,
        projection_years: int,
    ) -> FinancialForecast:
        periods = financial_analysis.periods_analyzed
        warnings: list[str] = []
        if len(periods) < 2:
            warnings.append(
                "Only one fiscal period of data is available; statement forecasts are unavailable."
            )

        income_by_period = {stmt.period: stmt for stmt in company_financials.income_statements}
        periods_elapsed = len(periods) - 1 if len(periods) >= 2 else None
        first_period = periods[0] if periods else None
        last_period = periods[-1] if periods else None

        metrics = [
            self._project_income_field(
                field_name, unit, income_by_period, first_period, last_period, periods_elapsed, projection_years
            )
            for field_name, unit in _INCOME_STATEMENT_METRICS
        ]
        metrics.append(
            self._project_free_cash_flow(financial_analysis, first_period, last_period, projection_years)
        )

        return FinancialForecast(
            company=financial_analysis.company,
            projection_years=projection_years,
            metrics=metrics,
            warnings=warnings,
        )

    def _project_income_field(
        self, field_name, unit, income_by_period, first_period, last_period, periods_elapsed, projection_years
    ):
        begin_stmt = income_by_period.get(first_period) if first_period else None
        end_stmt = income_by_period.get(last_period) if last_period else None
        begin_value = getattr(begin_stmt, field_name) if begin_stmt else None
        end_value = getattr(end_stmt, field_name) if end_stmt else None

        cagr, status, reason = calculate_cagr(begin_value, end_value, periods_elapsed)
        return project_metric(
            name=field_name,
            unit=unit,
            base_period=last_period,
            base_value=end_value,
            cagr_percent=cagr,
            cagr_status=status,
            cagr_reason=reason,
            periods_used=[p for p in (first_period, last_period) if p],
            projection_years=projection_years,
        )

    def _project_free_cash_flow(self, financial_analysis, first_period, last_period, projection_years):
        latest_fcf = next(
            (m for m in financial_analysis.metrics if m.name == "free_cash_flow"), None
        )
        fcf_growth = next(
            (m for m in financial_analysis.metrics if m.name == "fcf_growth"), None
        )

        end_value = latest_fcf.value if latest_fcf and latest_fcf.status is MetricStatus.CALCULATED else None

        # Step 2 only exposes the latest-vs-previous-period YoY growth, never
        # a full multi-period CAGR (that would need the earliest period's
        # derived FCF, not recomputed here) -- so this is the growth
        # assumption used, whatever the total period count. Its status and
        # reason are propagated verbatim rather than collapsed to a generic
        # "insufficient historical periods" message, so e.g. a FY-over-FY
        # sign flip (FCF turning positive/negative) is reported as INVALID
        # with its real reason, not misreported as missing history.
        if end_value is None:
            cagr, status, reason = None, MetricStatus.UNAVAILABLE, "free cash flow is unavailable for the latest period"
        elif fcf_growth is None:
            cagr, status, reason = None, MetricStatus.UNAVAILABLE, "insufficient historical periods to calculate an FCF growth trend"
        elif fcf_growth.status is MetricStatus.CALCULATED:
            cagr, status, reason = fcf_growth.value, MetricStatus.CALCULATED, None
        else:
            cagr, status, reason = None, fcf_growth.status, fcf_growth.reason

        return project_metric(
            name="free_cash_flow",
            unit="USD",
            base_period=last_period,
            base_value=end_value,
            cagr_percent=cagr,
            cagr_status=status,
            cagr_reason=reason,
            periods_used=[p for p in (first_period, last_period) if p],
            projection_years=projection_years,
        )

    # --- Valuation scenario forecasting -----------------------------------------------

    def forecast_valuation(
        self, valuation_input: ValuationInput, projection_years: int
    ) -> ValuationForecastRange:
        base_growth = valuation_input.fcf_growth_rate
        scenario_growth_rates: list[tuple[str, Decimal | None]] = (
            [
                ("bear", base_growth - _SCENARIO_SPREAD),
                ("base", base_growth),
                ("bull", base_growth + _SCENARIO_SPREAD),
            ]
            if base_growth is not None
            else [("bear", None), ("base", None), ("bull", None)]
        )

        scenarios = [
            ValuationScenario(
                scenario=name,
                fcf_growth_rate=growth_rate,
                result=calculate_dcf(
                    base_fcf=valuation_input.free_cash_flow,
                    fcf_growth_rate=growth_rate,
                    discount_rate=valuation_input.discount_rate,
                    terminal_growth_rate=valuation_input.terminal_growth_rate,
                    projection_years=valuation_input.projection_years or projection_years,
                    total_debt=valuation_input.total_debt,
                    cash=valuation_input.cash,
                    shares_outstanding=valuation_input.shares_outstanding,
                ),
            )
            for name, growth_rate in scenario_growth_rates
        ]

        warnings = []
        if base_growth is None:
            warnings.append(
                "No FCF growth rate assumption was supplied; valuation scenarios are unavailable."
            )

        return ValuationForecastRange(
            company=valuation_input.company_name,
            current_share_price=valuation_input.current_share_price,
            scenarios=scenarios,
            warnings=warnings,
        )

    # --- Price trend forecasting -------------------------------------------------------

    def forecast_price_trend(
        self,
        ticker: str,
        recent_prices: list[HistoricalPricePoint],
        projection_days: int,
        *,
        horizon: ForecastHorizon = ForecastHorizon.DAILY,
        period_offsets: list[tuple[int, int]] | None = None,
    ) -> PriceTrendForecast:
        """`period_offsets` is an optional list of `(period_number,
        trading_day_offset)` pairs the fitted line is evaluated at.
        Defaults to one point per trading day, `1..projection_days` (the
        original daily behavior). Weekly/monthly horizons reuse the exact
        same OLS fit computed below and only change which offsets it's
        evaluated at -- see `_build_multi_horizon_forecast`."""
        usable = sorted(
            (p for p in recent_prices if p.close is not None),
            key=lambda p: p.timestamp,
        )
        closes = [p.close for p in usable]

        slope, intercept, r_squared, status, reason = fit_linear_trend(closes)
        if status is not MetricStatus.CALCULATED:
            return PriceTrendForecast(
                ticker=ticker,
                horizon=horizon,
                based_on_points=len(closes),
                projection_days=projection_days,
                status=status,
                reason=reason,
            )

        last_index = Decimal(len(closes) - 1)
        anchor_date = usable[-1].timestamp if usable else None
        offsets = period_offsets or [(day, day) for day in range(1, projection_days + 1)]
        points = [
            PriceTrendPoint(
                period=period,
                day_offset=trading_days,
                date=project_trading_date(anchor_date, trading_days),
                # A share price cannot go negative; a steep downtrend
                # extrapolated far enough is floored at zero rather than
                # emitting an economically meaningless negative value.
                projected_price=max(Decimal(0), intercept + slope * (last_index + trading_days)),
            )
            for period, trading_days in offsets
        ]

        return PriceTrendForecast(
            ticker=ticker,
            horizon=horizon,
            based_on_points=len(closes),
            slope_per_day=slope,
            r_squared=r_squared,
            projection_days=projection_days,
            points=points,
            status=MetricStatus.CALCULATED,
        )

    # --- Technical indicator forecasting ------------------------------------------------

    def forecast_technical(
        self,
        ticker: str,
        recent_prices: list[HistoricalPricePoint],
        current_price: Decimal | None,
        projection_days: int,
        *,
        horizon: ForecastHorizon = ForecastHorizon.DAILY,
        horizon_period: int | None = None,
    ) -> TechnicalForecast:
        """Moving averages, crossover signal, and momentum-based
        projections -- each an independently-labeled technique so
        results can be tracked and compared against actual outcomes
        over time, exactly like `forecast_valuation`'s bear/base/bull
        scenarios are never blended into one number.

        `horizon_period` is the horizon's own period count this
        single-value projection targets (e.g. 12 for weekly/monthly);
        it defaults to `projection_days` so the original daily call
        (period == trading days) is unchanged."""
        resolved_horizon_period = horizon_period if horizon_period is not None else projection_days
        momentum_caution = "" if horizon is ForecastHorizon.DAILY else _MOMENTUM_HORIZON_CAUTION
        usable = sorted(
            (p for p in recent_prices if p.close is not None),
            key=lambda p: p.timestamp,
        )
        closes = [p.close for p in usable]
        # Fall back to the latest known close when no explicit current
        # price was supplied (e.g. called outside the pipeline's
        # market-data resolution step).
        resolved_current_price = current_price if current_price is not None else (closes[-1] if closes else None)
        anchor_date = usable[-1].timestamp if usable else None
        target_date = project_trading_date(anchor_date, projection_days)

        warnings: list[str] = []

        sma_50_value, sma_50_status, sma_50_reason = calculate_sma(closes, SMA_SHORT_WINDOW)
        sma_200_value, sma_200_status, sma_200_reason = calculate_sma(closes, SMA_LONG_WINDOW)
        moving_averages = [
            MovingAverageResult(window=SMA_SHORT_WINDOW, value=sma_50_value, status=sma_50_status, reason=sma_50_reason),
            MovingAverageResult(window=SMA_LONG_WINDOW, value=sma_200_value, status=sma_200_status, reason=sma_200_reason),
        ]
        if sma_50_status is not MetricStatus.CALCULATED:
            warnings.append(f"{SMA_SHORT_WINDOW}-day moving average unavailable: {sma_50_reason}")
        if sma_200_status is not MetricStatus.CALCULATED:
            warnings.append(f"{SMA_LONG_WINDOW}-day moving average unavailable: {sma_200_reason}")

        crossover_signal, crossover_status, crossover_reason = classify_moving_average_crossover(
            sma_50_value, sma_200_value
        )
        crossover = MovingAverageCrossover(
            short_window=SMA_SHORT_WINDOW,
            long_window=SMA_LONG_WINDOW,
            signal=crossover_signal,
            status=crossover_status,
            reason=crossover_reason,
        )

        methods: list[TechnicalForecastMethod] = []

        methods.append(
            self._sma_level_method(
                "sma_50",
                "50-day simple moving average, reported as the level recent price action is "
                "clustered around (a mean-reversion reference, not a directional forecast).",
                sma_50_value,
                sma_50_status,
                sma_50_reason,
                projection_days,
                target_date,
                horizon,
                resolved_horizon_period,
            )
        )
        methods.append(
            self._sma_level_method(
                "sma_200",
                "200-day simple moving average, reported as the level recent price action is "
                "clustered around (a mean-reversion reference, not a directional forecast).",
                sma_200_value,
                sma_200_status,
                sma_200_reason,
                projection_days,
                target_date,
                horizon,
                resolved_horizon_period,
            )
        )

        slope, intercept, _r_squared, trend_status, trend_reason = fit_linear_trend(closes)
        if trend_status is MetricStatus.CALCULATED:
            projected = intercept + slope * Decimal(len(closes) - 1 + projection_days)
            linear_value, linear_status, linear_reason = max(Decimal(0), projected), MetricStatus.CALCULATED, None
        else:
            linear_value, linear_status, linear_reason = None, trend_status, trend_reason
        methods.append(
            TechnicalForecastMethod(
                method="linear_regression",
                description="Ordinary least squares regression over recent closing prices, "
                "extrapolated forward by the projection horizon.",
                projected_price=linear_value,
                projection_days=projection_days,
                horizon=horizon,
                horizon_period=resolved_horizon_period,
                projected_date=target_date,
                status=linear_status,
                reason=linear_reason,
            )
        )

        if (
            sma_50_status is MetricStatus.CALCULATED
            and sma_200_status is MetricStatus.CALCULATED
            and resolved_current_price is not None
            and sma_200_value != 0
        ):
            spread = (sma_50_value - sma_200_value) / sma_200_value
            crossover_projected = resolved_current_price * (1 + spread)
            methods.append(
                TechnicalForecastMethod(
                    method="sma_crossover_momentum",
                    description="Applies the percentage spread between the 50-day and 200-day moving "
                    "averages to the current price as a momentum drift (golden cross -> upward "
                    "drift, death cross -> downward drift)." + momentum_caution,
                    projected_price=max(Decimal(0), crossover_projected),
                    projection_days=projection_days,
                    horizon=horizon,
                    horizon_period=resolved_horizon_period,
                    projected_date=target_date,
                    status=MetricStatus.CALCULATED,
                )
            )
        else:
            reason = (
                "both 50-day and 200-day moving averages and a current price are required"
                if resolved_current_price is not None
                else "current price is unavailable"
            )
            methods.append(
                TechnicalForecastMethod(
                    method="sma_crossover_momentum",
                    description="Applies the percentage spread between the 50-day and 200-day moving "
                    "averages to the current price as a momentum drift (golden cross -> upward "
                    "drift, death cross -> downward drift)." + momentum_caution,
                    projected_price=None,
                    projection_days=projection_days,
                    horizon=horizon,
                    horizon_period=resolved_horizon_period,
                    projected_date=target_date,
                    status=MetricStatus.UNAVAILABLE,
                    reason=reason,
                )
            )

        roc_value, roc_status, roc_reason = calculate_rate_of_change(closes, ROC_WINDOW)
        if roc_status is MetricStatus.CALCULATED and resolved_current_price is not None:
            roc_projected = resolved_current_price * (1 + roc_value / 100)
            methods.append(
                TechnicalForecastMethod(
                    method="rate_of_change_momentum",
                    description=f"Applies the {ROC_WINDOW}-day rate-of-change (momentum) to the "
                    "current price, assuming the recent trend continues at the same pace." + momentum_caution,
                    projected_price=max(Decimal(0), roc_projected),
                    projection_days=projection_days,
                    horizon=horizon,
                    horizon_period=resolved_horizon_period,
                    projected_date=target_date,
                    status=MetricStatus.CALCULATED,
                )
            )
        else:
            methods.append(
                TechnicalForecastMethod(
                    method="rate_of_change_momentum",
                    description=f"Applies the {ROC_WINDOW}-day rate-of-change (momentum) to the "
                    "current price, assuming the recent trend continues at the same pace." + momentum_caution,
                    projected_price=None,
                    projection_days=projection_days,
                    horizon=horizon,
                    horizon_period=resolved_horizon_period,
                    projected_date=target_date,
                    status=roc_status if roc_status is not MetricStatus.CALCULATED else MetricStatus.UNAVAILABLE,
                    reason=roc_reason or "current price is unavailable",
                )
            )

        return TechnicalForecast(
            ticker=ticker,
            horizon=horizon,
            based_on_points=len(closes),
            current_price=resolved_current_price,
            projection_days=projection_days,
            moving_averages=moving_averages,
            crossover=crossover,
            methods=methods,
            warnings=warnings,
        )

    @staticmethod
    def _sma_level_method(
        method, description, value, status, reason, projection_days, projected_date, horizon, horizon_period
    ) -> TechnicalForecastMethod:
        return TechnicalForecastMethod(
            method=method,
            description=description,
            projected_price=value if status is MetricStatus.CALCULATED else None,
            projection_days=projection_days,
            horizon=horizon,
            horizon_period=horizon_period,
            projected_date=projected_date,
            status=status,
            reason=None if status is MetricStatus.CALCULATED else reason,
        )

    # --- Multi-horizon forecasting -------------------------------------------------------

    def _build_multi_horizon_forecast(
        self,
        ticker: str,
        recent_prices: list[HistoricalPricePoint],
        current_price: Decimal | None,
        daily_price_trend: PriceTrendForecast,
        daily_technical: TechnicalForecast,
    ) -> MultiHorizonForecast:
        """Weekly and monthly reuse the exact same OLS trend fit
        (`forecast_price_trend`) and technical-indicator formulas
        (`forecast_technical`) the daily horizon already used above --
        only the trading-day offsets they're evaluated at change.
        Nothing here is a new calculation, and the daily entries are the
        SAME objects already computed by `forecast()`, not recomputed."""
        daily_periods, _daily_step, daily_label = _HORIZON_SPECS[ForecastHorizon.DAILY]
        horizons: dict[ForecastHorizon, HorizonForecast] = {
            ForecastHorizon.DAILY: HorizonForecast(
                horizon=ForecastHorizon.DAILY,
                label=daily_label,
                price_trend=daily_price_trend,
                technical=daily_technical,
            )
        }
        for horizon in (ForecastHorizon.WEEKLY, ForecastHorizon.MONTHLY):
            periods, trading_days_per_period, label = _HORIZON_SPECS[horizon]
            terminal_trading_days = periods * trading_days_per_period
            offsets = [(period, period * trading_days_per_period) for period in range(1, periods + 1)]
            price_trend = self.forecast_price_trend(
                ticker, recent_prices, terminal_trading_days, horizon=horizon, period_offsets=offsets
            )
            technical = self.forecast_technical(
                ticker, recent_prices, current_price, terminal_trading_days,
                horizon=horizon, horizon_period=periods,
            )
            horizons[horizon] = HorizonForecast(horizon=horizon, label=label, price_trend=price_trend, technical=technical)

        return MultiHorizonForecast(
            daily=horizons[ForecastHorizon.DAILY],
            weekly=horizons[ForecastHorizon.WEEKLY],
            monthly=horizons[ForecastHorizon.MONTHLY],
        )
