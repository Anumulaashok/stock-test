"""Centralized scoring thresholds and weights.

Every number that shapes a score or a risk severity lives here, named
and documented, instead of being buried inline in calculation code.
Values are on the same numeric scale Step 2/3 already use: percentage
metrics (margins, ROE, ROA, ROIC, growth rates, valuation upside) are
plain numbers where 25 means 25%, matching `FinancialMetricResult`'s
`as_percentage=True` convention; ratio metrics (debt/equity, current
ratio, interest coverage, ...) are the raw ratio.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.models.scoring import Severity


@dataclass(frozen=True)
class LinearBand:
    """A value range that scores 0 at `floor` and 100 at `target` (or the
    reverse for lower-is-better metrics), clamped outside that range so a
    single extreme value cannot dominate a category or crash the engine.
    """

    floor: Decimal
    target: Decimal


# --- Profitability (higher is better) ------------------------------------------
# Targets are generous-but-attainable "strong performance" levels for a
# healthy company; floors are 0 (no profitability = no credit).

ROE_BAND = LinearBand(Decimal(0), Decimal(25))
ROA_BAND = LinearBand(Decimal(0), Decimal(15))
ROIC_BAND = LinearBand(Decimal(0), Decimal(20))
GROSS_MARGIN_BAND = LinearBand(Decimal(0), Decimal(60))
OPERATING_MARGIN_BAND = LinearBand(Decimal(0), Decimal(30))
NET_MARGIN_BAND = LinearBand(Decimal(0), Decimal(20))
FCF_MARGIN_BAND = LinearBand(Decimal(0), Decimal(20))

PROFITABILITY_WEIGHTS = {
    "gross_margin": Decimal("0.10"),
    "operating_margin": Decimal("0.15"),
    "net_margin": Decimal("0.20"),
    "fcf_margin": Decimal("0.15"),
    "roe": Decimal("0.20"),
    "roa": Decimal("0.10"),
    "roic": Decimal("0.10"),
}

# --- Growth (higher is better, but capped so no single outlier dominates) ------
# Floors are mildly negative (a small decline is not treated as a
# complete zero) and targets cap credit at a strong-but-plausible rate,
# so a 400% one-off growth number scores the same as a 40% one.

REVENUE_GROWTH_BAND = LinearBand(Decimal(-10), Decimal(30))
NET_INCOME_GROWTH_BAND = LinearBand(Decimal(-20), Decimal(40))
EPS_GROWTH_BAND = LinearBand(Decimal(-20), Decimal(40))
FCF_GROWTH_BAND = LinearBand(Decimal(-20), Decimal(40))

GROWTH_WEIGHTS = {
    "revenue_growth": Decimal("0.35"),
    "net_income_growth": Decimal("0.30"),
    "eps_growth": Decimal("0.20"),
    "fcf_growth": Decimal("0.15"),
}

# --- Financial health -----------------------------------------------------------

INTEREST_COVERAGE_BAND = LinearBand(Decimal(0), Decimal(10))  # higher is better
CASH_RATIO_BAND = LinearBand(Decimal(0), Decimal(1))  # higher is better
DEBT_TO_EQUITY_BAND = LinearBand(Decimal(0), Decimal(2))  # lower is better
DEBT_TO_FCF_BAND = LinearBand(Decimal(0), Decimal(10))  # lower is better

# Current ratio gets a dedicated "sweet spot" shape rather than a simple
# band: below 1.0 is a genuine liquidity danger zone; 1.5-3.0 is
# considered healthy and scores the maximum; beyond that, capital is
# increasingly sitting idle, so the score drifts down gently (never to
# zero) rather than rewarding an ever-higher ratio indefinitely.
CURRENT_RATIO_DANGER = Decimal("1.0")
CURRENT_RATIO_IDEAL_LOW = Decimal("1.5")
CURRENT_RATIO_IDEAL_HIGH = Decimal("3.0")
CURRENT_RATIO_EXCESSIVE = Decimal("6.0")
CURRENT_RATIO_DANGER_SCORE = Decimal(60)  # score at the ratio == 1.0 boundary
CURRENT_RATIO_EXCESSIVE_SCORE = Decimal(70)  # floor score once ratio >= 6.0

FINANCIAL_HEALTH_WEIGHTS = {
    "current_ratio": Decimal("0.20"),
    "cash_ratio": Decimal("0.15"),
    "debt_to_equity": Decimal("0.30"),
    "debt_to_fcf": Decimal("0.15"),
    "interest_coverage": Decimal("0.20"),
}

# --- Cash flow --------------------------------------------------------------------
# Raw FCF dollar magnitude is not comparable across companies of very
# different sizes, so the `free_cash_flow` component only scores its
# sign (positive/zero/negative); scale-aware nuance comes from
# `fcf_margin` and `fcf_growth`, which are already normalized ratios.

FCF_SIGN_POSITIVE_SCORE = Decimal(100)
FCF_SIGN_ZERO_SCORE = Decimal(50)
FCF_SIGN_NEGATIVE_SCORE = Decimal(0)

CASH_FLOW_WEIGHTS = {
    "free_cash_flow": Decimal("0.30"),
    "fcf_margin": Decimal("0.40"),
    "fcf_growth": Decimal("0.30"),
}

# --- Valuation --------------------------------------------------------------------
# Upside/downside (already a percentage) maps linearly onto 0-100:
# -30% or worse (significantly overvalued) scores 0, +50% or better
# (significantly undervalued) scores 100.

VALUATION_UPSIDE_BAND = LinearBand(Decimal(-30), Decimal(50))

# Explicit, documented per-method weights — deliberately not an average.
# DCF is weighted highest as the most fundamentals-driven method; EV/EBITDA
# next (capital-structure neutral); P/E and P/FCF lowest since single
# earnings/cash-flow multiples are the most exposed to accounting noise
# and one-off items.
VALUATION_METHOD_WEIGHTS = {
    "dcf": Decimal("0.40"),
    "ev_ebitda": Decimal("0.25"),
    "pe": Decimal("0.20"),
    "pfcf": Decimal("0.15"),
}

# --- Overall category weights (must sum to 1.00) --------------------------------

CATEGORY_WEIGHTS = {
    "profitability": Decimal("0.20"),
    "growth": Decimal("0.15"),
    "financial_health": Decimal("0.20"),
    "cash_flow": Decimal("0.15"),
    "valuation": Decimal("0.20"),
    "risk": Decimal("0.10"),
}

# --- Risk indicator thresholds ----------------------------------------------------
# Each is an explicit, descending list of (threshold, severity) checked
# from most to least severe; the first threshold the measured value
# breaches determines severity.

DEBT_TO_EQUITY_RISK_THRESHOLDS: list[tuple[Decimal, Severity]] = [
    (Decimal(5), Severity.CRITICAL),
    (Decimal(3), Severity.HIGH),
    (Decimal(2), Severity.MEDIUM),
]

INTEREST_COVERAGE_RISK_THRESHOLDS: list[tuple[Decimal, Severity]] = [
    (Decimal(1), Severity.CRITICAL),
    (Decimal(2), Severity.HIGH),
    (Decimal(4), Severity.MEDIUM),
]

CURRENT_RATIO_RISK_THRESHOLDS: list[tuple[Decimal, Severity]] = [
    (Decimal("0.5"), Severity.CRITICAL),
    (Decimal("0.8"), Severity.HIGH),
    (Decimal("1.0"), Severity.MEDIUM),
]

# Applied only once a value is already confirmed negative (any decline is
# at least LOW severity by default; these two cutoffs escalate it).
DECLINE_RISK_THRESHOLDS: list[tuple[Decimal, Severity]] = [
    (Decimal(-20), Severity.HIGH),
    (Decimal(-10), Severity.MEDIUM),
]

EXCESSIVE_VALUATION_RISK_THRESHOLDS: list[tuple[Decimal, Severity]] = [
    (Decimal(-40), Severity.HIGH),
    (Decimal(-20), Severity.MEDIUM),
]

MISSING_DATA_RISK_THRESHOLDS: list[tuple[int, Severity]] = [
    (3, Severity.HIGH),
    (1, Severity.MEDIUM),
]

# Severity -> penalty applied when converting risk indicators into the
# Risk category's 0-100 score (100 - penalty, clamped at 0).
RISK_SEVERITY_PENALTY = {
    Severity.LOW: Decimal(10),
    Severity.MEDIUM: Decimal(30),
    Severity.HIGH: Decimal(60),
    Severity.CRITICAL: Decimal(100),
}

# --- Score interpretation bands (descriptive only, not a recommendation) -------

SCORE_BAND_THRESHOLDS = [
    (Decimal(90), "excellent"),
    (Decimal(80), "strong"),
    (Decimal(70), "good"),
    (Decimal(60), "fair"),
    (Decimal(40), "weak"),
    (Decimal(0), "poor"),
]
