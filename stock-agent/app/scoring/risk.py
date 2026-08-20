"""Deterministic risk indicators.

Each check reads one or more Step 2/3 metrics and reports a fixed,
threshold-driven severity — never a subjective judgment. A metric that
is itself unavailable or invalid makes its risk check unavailable too
(the engine reports "cannot assess" rather than guessing).
"""

from decimal import Decimal

from app.models.financial_results import FinancialMetricResult
from app.models.financial_results import MetricStatus as FinancialMetricStatus
from app.models.scoring import CategoryScore, RiskIndicator, ScoreComponent, ScoreStatus, Severity
from app.models.valuation import ValuationRange
from app.scoring.aggregation import aggregate_category
from app.scoring.thresholds import (
    CURRENT_RATIO_RISK_THRESHOLDS,
    DEBT_TO_EQUITY_RISK_THRESHOLDS,
    DECLINE_RISK_THRESHOLDS,
    EXCESSIVE_VALUATION_RISK_THRESHOLDS,
    INTEREST_COVERAGE_RISK_THRESHOLDS,
    MISSING_DATA_RISK_THRESHOLDS,
    RISK_SEVERITY_PENALTY,
)

_ZERO = Decimal(0)

# Metrics whose absence materially limits how much this engine can assess.
_CRITICAL_METRICS = ["free_cash_flow", "net_margin", "debt_to_equity", "current_ratio"]


def _first_match_at_or_above(value: Decimal, thresholds) -> Severity | None:
    for threshold, severity in thresholds:
        if value >= threshold:
            return severity
    return None


def _first_match_at_or_below(value: Decimal, thresholds) -> Severity | None:
    for threshold, severity in thresholds:
        if value <= threshold:
            return severity
    return None


def _decline_severity(value: Decimal) -> Severity | None:
    if value >= 0:
        return None
    return _first_match_at_or_below(value, DECLINE_RISK_THRESHOLDS) or Severity.LOW


def _unavailable_indicator(name: str, metric: FinancialMetricResult | None, fallback_reason: str) -> RiskIndicator:
    if metric is None:
        return RiskIndicator(name=name, status=ScoreStatus.UNAVAILABLE, reason=fallback_reason)
    status = (
        ScoreStatus.INVALID
        if metric.status is FinancialMetricStatus.INVALID
        else ScoreStatus.UNAVAILABLE
    )
    return RiskIndicator(name=name, status=status, reason=metric.reason or fallback_reason)


def _check_negative_fcf(metrics: dict[str, FinancialMetricResult]) -> RiskIndicator:
    name = "negative_fcf"
    metric = metrics.get("free_cash_flow")
    if metric is None or metric.status is not FinancialMetricStatus.CALCULATED:
        return _unavailable_indicator(name, metric, "free cash flow metric was not provided")
    if metric.value < 0:
        return RiskIndicator(
            name=name, severity=Severity.HIGH, status=ScoreStatus.CALCULATED,
            value=metric.value, threshold=_ZERO, reason="free cash flow is negative",
        )
    return RiskIndicator(
        name=name, status=ScoreStatus.CALCULATED, value=metric.value, threshold=_ZERO,
        reason="free cash flow is not negative",
    )


def _check_negative_net_income(metrics: dict[str, FinancialMetricResult]) -> RiskIndicator:
    name = "negative_net_income"
    metric = metrics.get("net_margin")
    if metric is None or metric.status is not FinancialMetricStatus.CALCULATED:
        return _unavailable_indicator(
            name, metric, "net margin metric (used as a proxy for net income) was not provided"
        )
    if metric.value < 0:
        return RiskIndicator(
            name=name, severity=Severity.HIGH, status=ScoreStatus.CALCULATED,
            value=metric.value, threshold=_ZERO,
            reason="net margin is negative, implying a net loss",
        )
    return RiskIndicator(
        name=name, status=ScoreStatus.CALCULATED, value=metric.value, threshold=_ZERO,
        reason="net margin is not negative",
    )


def _check_high_debt_to_equity(metrics: dict[str, FinancialMetricResult]) -> RiskIndicator:
    name = "high_debt_to_equity"
    metric = metrics.get("debt_to_equity")
    if metric is None or metric.status is not FinancialMetricStatus.CALCULATED:
        return _unavailable_indicator(name, metric, "debt/equity metric was not provided")
    severity = _first_match_at_or_above(metric.value, DEBT_TO_EQUITY_RISK_THRESHOLDS)
    reason = (
        f"debt/equity of {metric.value} is at or above the {severity.value} risk threshold"
        if severity
        else "debt/equity is within an acceptable range"
    )
    return RiskIndicator(
        name=name, severity=severity, status=ScoreStatus.CALCULATED,
        value=metric.value, threshold=DEBT_TO_EQUITY_RISK_THRESHOLDS[-1][0], reason=reason,
    )


def _check_weak_interest_coverage(metrics: dict[str, FinancialMetricResult]) -> RiskIndicator:
    name = "weak_interest_coverage"
    metric = metrics.get("interest_coverage")
    if metric is None or metric.status is not FinancialMetricStatus.CALCULATED:
        return _unavailable_indicator(name, metric, "interest coverage metric was not provided")
    severity = _first_match_at_or_below(metric.value, INTEREST_COVERAGE_RISK_THRESHOLDS)
    reason = (
        f"interest coverage of {metric.value} is at or below the {severity.value} risk threshold"
        if severity
        else "interest coverage is within an acceptable range"
    )
    return RiskIndicator(
        name=name, severity=severity, status=ScoreStatus.CALCULATED,
        value=metric.value, threshold=INTEREST_COVERAGE_RISK_THRESHOLDS[-1][0], reason=reason,
    )


def _check_weak_liquidity(metrics: dict[str, FinancialMetricResult]) -> RiskIndicator:
    name = "weak_liquidity"
    metric = metrics.get("current_ratio")
    if metric is None or metric.status is not FinancialMetricStatus.CALCULATED:
        return _unavailable_indicator(name, metric, "current ratio metric was not provided")
    severity = _first_match_at_or_below(metric.value, CURRENT_RATIO_RISK_THRESHOLDS)
    reason = (
        f"current ratio of {metric.value} is at or below the {severity.value} risk threshold"
        if severity
        else "current ratio is within an acceptable range"
    )
    return RiskIndicator(
        name=name, severity=severity, status=ScoreStatus.CALCULATED,
        value=metric.value, threshold=CURRENT_RATIO_RISK_THRESHOLDS[-1][0], reason=reason,
    )


def _check_decline(
    metrics: dict[str, FinancialMetricResult], metric_name: str, indicator_name: str, label: str
) -> RiskIndicator:
    metric = metrics.get(metric_name)
    if metric is None or metric.status is not FinancialMetricStatus.CALCULATED:
        return _unavailable_indicator(indicator_name, metric, f"{label} metric was not provided")
    severity = _decline_severity(metric.value)
    reason = f"{label} is declining" if severity else f"{label} is not declining"
    return RiskIndicator(
        name=indicator_name, severity=severity, status=ScoreStatus.CALCULATED,
        value=metric.value, threshold=_ZERO, reason=reason,
    )


def _check_excessive_valuation(valuation: ValuationRange | None) -> RiskIndicator:
    name = "excessive_valuation"
    if valuation is None or not valuation.results:
        return RiskIndicator(name=name, status=ScoreStatus.UNAVAILABLE, reason="no valuation data was provided")

    # Prefer DCF as the most fundamentals-driven method; fall back to the
    # first method with a calculated upside/downside.
    candidates = sorted(valuation.results, key=lambda r: 0 if r.method == "dcf" else 1)
    chosen = next(
        (r for r in candidates if r.upside_downside_percent is not None),
        None,
    )
    if chosen is None:
        return RiskIndicator(
            name=name, status=ScoreStatus.UNAVAILABLE,
            reason="no valuation method had a calculated upside/downside against the current price",
        )

    value = chosen.upside_downside_percent
    severity = _first_match_at_or_below(value, EXCESSIVE_VALUATION_RISK_THRESHOLDS)
    reason = (
        f"{chosen.method} implies {value}% downside, at or below the {severity.value} risk threshold"
        if severity
        else f"{chosen.method} valuation is not excessive"
    )
    return RiskIndicator(
        name=name, severity=severity, status=ScoreStatus.CALCULATED,
        value=value, threshold=EXCESSIVE_VALUATION_RISK_THRESHOLDS[-1][0], reason=reason,
    )


def _check_missing_critical_data(metrics: dict[str, FinancialMetricResult]) -> RiskIndicator:
    name = "missing_critical_data"
    missing = [
        metric_name
        for metric_name in _CRITICAL_METRICS
        if metrics.get(metric_name) is None
        or metrics[metric_name].status is not FinancialMetricStatus.CALCULATED
    ]
    severity = None
    for threshold, tier in MISSING_DATA_RISK_THRESHOLDS:
        if len(missing) >= threshold:
            severity = tier
            break
    reason = (
        f"{len(missing)} of {len(_CRITICAL_METRICS)} critical metrics are missing or unusable: "
        f"{', '.join(missing)}"
        if missing
        else "all critical metrics are available"
    )
    return RiskIndicator(
        name=name, severity=severity, status=ScoreStatus.CALCULATED,
        value=Decimal(len(missing)), threshold=Decimal(MISSING_DATA_RISK_THRESHOLDS[-1][0]), reason=reason,
    )


def detect_risk_indicators(
    metrics: dict[str, FinancialMetricResult], valuation: ValuationRange | None
) -> list[RiskIndicator]:
    """Run every risk check. Never raises — missing data yields an
    `unavailable` indicator, not an exception."""
    return [
        _check_negative_fcf(metrics),
        _check_negative_net_income(metrics),
        _check_high_debt_to_equity(metrics),
        _check_weak_interest_coverage(metrics),
        _check_weak_liquidity(metrics),
        _check_decline(metrics, "revenue_growth", "declining_revenue", "revenue growth"),
        _check_decline(metrics, "net_income_growth", "declining_net_income", "net income growth"),
        _check_excessive_valuation(valuation),
        _check_decline(metrics, "fcf_growth", "weak_cash_flow_trend", "FCF growth"),
        _check_missing_critical_data(metrics),
    ]


def calculate_risk_score(indicators: list[RiskIndicator], category_weight: Decimal) -> CategoryScore:
    """Convert risk indicators into the Risk category's 0-100 score.

    Each CALCULATED indicator becomes an equally-weighted component:
    100 if not triggered, `100 - severity penalty` (floored at 0) if
    triggered. Higher score = lower risk, matching every other category's
    "higher is better" convention.
    """
    equal_weight = Decimal(1) / Decimal(len(indicators)) if indicators else Decimal(0)
    components = []
    for indicator in indicators:
        if indicator.status != ScoreStatus.CALCULATED:
            components.append(
                ScoreComponent(
                    name=indicator.name, score=None, weight=equal_weight,
                    status=indicator.status, reason=indicator.reason, source_metric=indicator.name,
                )
            )
            continue
        if indicator.severity is None:
            score = Decimal(100)
        else:
            penalty = RISK_SEVERITY_PENALTY[indicator.severity]
            score = max(Decimal(100) - penalty, Decimal(0))
        components.append(
            ScoreComponent(
                name=indicator.name, score=score, weight=equal_weight,
                status=ScoreStatus.CALCULATED, reason=indicator.reason,
                source_metric=indicator.name, value=indicator.value,
            )
        )

    return aggregate_category("risk", components, category_weight)
