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

from app.forecasting.calculations import calculate_cagr, fit_linear_trend, project_metric
from app.models.financial_results import FinancialAnalysisResult, MetricStatus
from app.models.financial_statements import CompanyFinancials
from app.models.forecasting import (
    FinancialForecast,
    ForecastResult,
    PriceTrendForecast,
    PriceTrendPoint,
    ValuationForecastRange,
    ValuationScenario,
)
from app.models.market import HistoricalPricePoint
from app.models.valuation import ValuationInput
from app.valuation.dcf import calculate_dcf

_SCENARIO_SPREAD = Decimal("0.02")  # +/- 200 bps around the base FCF growth assumption
DEFAULT_PROJECTION_YEARS = 5
DEFAULT_PROJECTION_DAYS = 30

_INCOME_STATEMENT_METRICS = [
    ("revenue", "USD"),
    ("net_income", "USD"),
    ("eps", "USD"),
]


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
        price_trend_forecast = self.forecast_price_trend(
            ticker or company_financials.ticker or company_financials.company_name,
            recent_prices or [],
            projection_days,
        )

        warnings: list[str] = []
        warnings.extend(financial_forecast.warnings)
        if valuation_forecast:
            warnings.extend(valuation_forecast.warnings)

        return ForecastResult(
            company=company_financials.company_name,
            financial_forecast=financial_forecast,
            valuation_forecast=valuation_forecast,
            price_trend_forecast=price_trend_forecast,
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

        if end_value is None:
            cagr, status, reason = None, MetricStatus.UNAVAILABLE, "free cash flow is unavailable for the latest period"
        elif fcf_growth is None or fcf_growth.status is not MetricStatus.CALCULATED:
            # Step 2 only exposes the latest-vs-previous-period YoY growth,
            # never a full multi-period CAGR (that would need the earliest
            # period's derived FCF, not recomputed here) -- so this is the
            # growth assumption used, whatever the total period count.
            cagr, status, reason = None, MetricStatus.UNAVAILABLE, "insufficient historical periods to calculate an FCF growth trend"
        else:
            cagr, status, reason = fcf_growth.value, MetricStatus.CALCULATED, None

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
    ) -> PriceTrendForecast:
        usable = sorted(
            (p for p in recent_prices if p.close is not None),
            key=lambda p: p.timestamp,
        )
        closes = [p.close for p in usable]

        slope, intercept, r_squared, status, reason = fit_linear_trend(closes)
        if status is not MetricStatus.CALCULATED:
            return PriceTrendForecast(
                ticker=ticker,
                based_on_points=len(closes),
                projection_days=projection_days,
                status=status,
                reason=reason,
            )

        last_index = Decimal(len(closes) - 1)
        points = [
            PriceTrendPoint(
                day_offset=day,
                # A share price cannot go negative; a steep downtrend
                # extrapolated far enough is floored at zero rather than
                # emitting an economically meaningless negative value.
                projected_price=max(Decimal(0), intercept + slope * (last_index + day)),
            )
            for day in range(1, projection_days + 1)
        ]

        return PriceTrendForecast(
            ticker=ticker,
            based_on_points=len(closes),
            slope_per_day=slope,
            r_squared=r_squared,
            projection_days=projection_days,
            points=points,
            status=MetricStatus.CALCULATED,
        )
