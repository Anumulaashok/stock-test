"""Financial analysis service.

Orchestrates the calculation engine: aligns income statement, balance
sheet, and cash flow data by fiscal period, sorts periods chronologically,
and assembles the resulting metrics into a `FinancialAnalysisResult`.

This module contains the only "wiring" logic in the financial package —
it does not itself perform any financial math (see `calculations.py`)
and performs no I/O.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.financial import calculations as calc
from app.financial.periods import period_sort_key
from app.models.financial_results import (
    FinancialAnalysisResult,
    FinancialMetricResult,
    MetricStatus,
)
from app.models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFinancials,
    IncomeStatement,
)


@dataclass
class _PeriodBundle:
    period: str
    income: IncomeStatement | None
    balance: BalanceSheet | None
    cash_flow: CashFlowStatement | None


def _build_period_bundles(financials: CompanyFinancials) -> list[_PeriodBundle]:
    bundles: dict[str, _PeriodBundle] = {}

    def bundle_for(period: str) -> _PeriodBundle:
        if period not in bundles:
            bundles[period] = _PeriodBundle(
                period=period, income=None, balance=None, cash_flow=None
            )
        return bundles[period]

    for stmt in financials.income_statements:
        bundle_for(stmt.period).income = stmt
    for stmt in financials.balance_sheets:
        bundle_for(stmt.period).balance = stmt
    for stmt in financials.cash_flow_statements:
        bundle_for(stmt.period).cash_flow = stmt

    return sorted(bundles.values(), key=lambda b: period_sort_key(b.period))


def _effective_fcf(bundle: _PeriodBundle) -> FinancialMetricResult:
    """The FCF metric to use for `bundle`'s period.

    Prefers a directly stated `free_cash_flow` value; falls back to
    deriving it from operating cash flow and capital expenditure.
    """
    stated = bundle.cash_flow.free_cash_flow if bundle.cash_flow else None
    if stated is not None:
        return FinancialMetricResult(
            name="free_cash_flow",
            value=stated,
            unit="USD",
            status=MetricStatus.CALCULATED,
            source_periods=[bundle.period],
        )
    ocf = bundle.cash_flow.operating_cash_flow if bundle.cash_flow else None
    capex = bundle.cash_flow.capital_expenditure if bundle.cash_flow else None
    return calc.calculate_free_cash_flow(ocf, capex, bundle.period)


class FinancialAnalysisService:
    """Runs the deterministic calculation engine over a company's financials."""

    def analyze(self, financials: CompanyFinancials) -> FinancialAnalysisResult:
        bundles = _build_period_bundles(financials)

        if not bundles:
            return FinancialAnalysisResult(
                company=financials.company_name,
                periods_analyzed=[],
                metrics=[],
                warnings=["No financial statement data was provided."],
            )

        periods_analyzed = [b.period for b in bundles]
        latest = bundles[-1]
        previous = bundles[-2] if len(bundles) >= 2 else None

        warnings: list[str] = []
        if previous is None:
            warnings.append(
                "Only one fiscal period of data is available; growth metrics are unavailable."
            )

        metrics: list[FinancialMetricResult] = []

        latest_fcf = _effective_fcf(latest)
        metrics.append(latest_fcf)

        metrics.extend(self._growth_metrics(previous, latest))
        metrics.extend(self._profitability_metrics(latest, latest_fcf))
        metrics.extend(self._leverage_metrics(latest, latest_fcf))
        metrics.extend(self._liquidity_metrics(latest))
        metrics.extend(self._coverage_metrics(latest))

        return FinancialAnalysisResult(
            company=financials.company_name,
            periods_analyzed=periods_analyzed,
            metrics=metrics,
            warnings=warnings,
        )

    def _growth_metrics(
        self, previous: _PeriodBundle | None, latest: _PeriodBundle
    ) -> list[FinancialMetricResult]:
        if previous is None:
            unavailable = "insufficient historical periods to calculate growth"
            return [
                FinancialMetricResult(
                    name=name,
                    value=None,
                    unit="%",
                    status=MetricStatus.UNAVAILABLE,
                    reason=unavailable,
                    source_periods=[latest.period],
                )
                for name in (
                    "revenue_growth",
                    "net_income_growth",
                    "eps_growth",
                    "fcf_growth",
                )
            ]

        prev_income = previous.income
        latest_income = latest.income

        def field(stmt: IncomeStatement | None, name: str) -> Decimal | None:
            return getattr(stmt, name) if stmt else None

        previous_fcf = _effective_fcf(previous)
        latest_fcf = _effective_fcf(latest)

        return [
            calc.calculate_revenue_growth(
                field(prev_income, "revenue"),
                field(latest_income, "revenue"),
                previous.period,
                latest.period,
            ),
            calc.calculate_net_income_growth(
                field(prev_income, "net_income"),
                field(latest_income, "net_income"),
                previous.period,
                latest.period,
            ),
            calc.calculate_eps_growth(
                field(prev_income, "eps"),
                field(latest_income, "eps"),
                previous.period,
                latest.period,
            ),
            calc.calculate_fcf_growth(
                previous_fcf.value,
                latest_fcf.value,
                previous.period,
                latest.period,
            ),
        ]

    def _profitability_metrics(
        self, latest: _PeriodBundle, latest_fcf: FinancialMetricResult
    ) -> list[FinancialMetricResult]:
        income = latest.income
        balance = latest.balance
        period = latest.period

        revenue = income.revenue if income else None

        return [
            calc.calculate_gross_margin(revenue, income.gross_profit if income else None, period),
            calc.calculate_operating_margin(
                revenue, income.operating_income if income else None, period
            ),
            calc.calculate_net_margin(revenue, income.net_income if income else None, period),
            calc.calculate_fcf_margin(revenue, latest_fcf.value, period),
            calc.calculate_roe(
                income.net_income if income else None,
                balance.shareholders_equity if balance else None,
                period,
            ),
            calc.calculate_roa(
                income.net_income if income else None,
                balance.total_assets if balance else None,
                period,
            ),
            calc.calculate_roic(
                income.operating_income if income else None,
                income.tax_expense if income else None,
                income.net_income if income else None,
                balance.total_debt if balance else None,
                balance.shareholders_equity if balance else None,
                balance.cash_and_equivalents if balance else None,
                period,
            ),
        ]

    def _leverage_metrics(
        self, latest: _PeriodBundle, latest_fcf: FinancialMetricResult
    ) -> list[FinancialMetricResult]:
        balance = latest.balance
        period = latest.period
        total_debt = balance.total_debt if balance else None

        return [
            calc.calculate_debt_to_equity(
                total_debt, balance.shareholders_equity if balance else None, period
            ),
            calc.calculate_debt_to_fcf(total_debt, latest_fcf.value, period),
        ]

    def _liquidity_metrics(self, latest: _PeriodBundle) -> list[FinancialMetricResult]:
        balance = latest.balance
        period = latest.period
        current_liabilities = balance.current_liabilities if balance else None

        return [
            calc.calculate_current_ratio(
                balance.current_assets if balance else None, current_liabilities, period
            ),
            calc.calculate_cash_ratio(
                balance.cash_and_equivalents if balance else None, current_liabilities, period
            ),
        ]

    def _coverage_metrics(self, latest: _PeriodBundle) -> list[FinancialMetricResult]:
        income = latest.income
        period = latest.period
        return [
            calc.calculate_interest_coverage(
                income.operating_income if income else None,
                income.interest_expense if income else None,
                period,
            )
        ]
