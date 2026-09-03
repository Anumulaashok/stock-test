"""Canonical units, periods, conflict resolution, and provider-symbol
resolution — the pure layer the source manager is built on."""

from decimal import Decimal

import pytest

from app.sources.capabilities import Capability, Category, can_serve
from app.sources.conflict import (
    ConflictStatus,
    MetricObservation,
    Resolution,
    resolve_observations,
)
from app.sources.identity import (
    CompanyIdentityResolver,
    Exchange,
    strip_exchange_suffix,
    to_yfinance_symbol,
)
from app.sources.periods import PeriodType, normalize_period, same_period
from app.sources.registry import FMP, INDIANAPI, SCREENER, YFINANCE, SourceRegistry
from app.sources.units import CanonicalUnit, UnitConversionError, convert, to_base

# --- Symbol resolution -------------------------------------------------------


@pytest.mark.parametrize("ticker", ["RECLTD", "HUDCO", "PFC", "IRFC", "NHPC"])
def test_nse_tickers_get_the_ns_suffix(ticker):
    assert to_yfinance_symbol(ticker) == f"{ticker}.NS"


@pytest.mark.parametrize("symbol", ["^NSEI", "^BSESN"])
def test_index_symbols_pass_through_untouched(symbol):
    assert to_yfinance_symbol(symbol) == symbol


def test_already_suffixed_symbols_are_not_double_suffixed():
    assert to_yfinance_symbol("RELIANCE.NS") == "RELIANCE.NS"
    assert to_yfinance_symbol("RELIANCE.BO") == "RELIANCE.BO"


def test_bse_exchange_uses_its_own_suffix():
    assert to_yfinance_symbol("RECLTD", Exchange.BSE) == "RECLTD.BO"


def test_unknown_exchange_does_not_guess_a_suffix():
    assert to_yfinance_symbol("AAPL", Exchange.UNKNOWN) == "AAPL"


def test_canonical_ticker_stays_bare():
    identity = CompanyIdentityResolver().resolve_offline("  recltd.ns ")
    assert identity.canonical_ticker == "RECLTD"
    assert identity.yfinance_symbol == "RECLTD.NS"
    assert strip_exchange_suffix("RECLTD.NS") == "RECLTD"


def test_index_identity_has_no_exchange():
    identity = CompanyIdentityResolver().resolve_offline("^NSEI")
    assert identity.is_index
    assert identity.exchange == Exchange.UNKNOWN
    assert identity.yfinance_symbol == "^NSEI"


# --- Period normalization ----------------------------------------------------


@pytest.mark.parametrize("raw", ["FY2026", "2026-03-31", "Mar 2026", "March 2026", "2026", "fy26"])
def test_equivalent_annual_periods_normalize_together(raw):
    period = normalize_period(raw)
    assert period.label == "FY2026"
    assert period.period_type == PeriodType.ANNUAL
    assert period.fiscal_year == 2026


def test_interim_date_is_not_relabelled_as_annual():
    period = normalize_period("2025-12-31")
    assert period.period_type == PeriodType.QUARTERLY
    # Dec 2025 falls inside FY2026 (April 2025 - March 2026).
    assert period.fiscal_year == 2026
    assert period.label == "2025-12-31"


def test_unrecognized_period_is_preserved_not_guessed():
    period = normalize_period("second half")
    assert period.label == "second half"
    assert period.period_type == PeriodType.UNKNOWN
    assert period.fiscal_year is None


def test_empty_period_is_unknown():
    assert normalize_period(None).period_type == PeriodType.UNKNOWN
    assert normalize_period("  ").label == "UNKNOWN"


def test_same_period_across_formats():
    assert same_period("FY2026", "Mar 2026")
    assert not same_period("FY2026", "FY2025")
    assert not same_period("FY2026", "2025-12-31")


# --- Unit normalization ------------------------------------------------------


def test_crore_to_inr():
    assert convert(Decimal("12843"), CanonicalUnit.INR_CRORE, CanonicalUnit.INR) == Decimal("128430000000")


def test_inr_to_crore_round_trips():
    value = Decimal("128430000000")
    assert convert(value, CanonicalUnit.INR, CanonicalUnit.INR_CRORE) == Decimal("12843")


def test_percent_and_ratio_are_one_family():
    assert convert(Decimal("15"), CanonicalUnit.PERCENT, CanonicalUnit.RATIO) == Decimal("0.15")


def test_incompatible_families_raise_rather_than_silently_passing_through():
    with pytest.raises(UnitConversionError):
        convert(Decimal("5"), CanonicalUnit.INR, CanonicalUnit.PERCENT)
    with pytest.raises(UnitConversionError):
        convert(Decimal("5"), CanonicalUnit.SHARES, CanonicalUnit.INR)


def test_to_base_makes_differently_scaled_values_comparable():
    crore = to_base(Decimal("12843"), CanonicalUnit.INR_CRORE)
    plain = to_base(Decimal("128430000000"), CanonicalUnit.INR)
    assert crore == plain


# --- Conflict resolution -----------------------------------------------------


def _obs(source, value, unit=CanonicalUnit.INR_CRORE, period="FY2026"):
    return MetricObservation(
        metric="revenue", value=Decimal(value), unit=unit, period=period, source=source
    )


def test_single_observation_is_not_a_conflict():
    result = resolve_observations([_obs("indianapi", "12843")])
    assert result.status == ConflictStatus.SINGLE_SOURCE
    assert result.resolution == Resolution.ONLY_OBSERVATION
    assert result.selected.source == "indianapi"


def test_small_difference_is_agreement_and_primary_wins():
    result = resolve_observations([_obs("indianapi", "12843"), _obs("fmp", "12841")])
    assert result.status == ConflictStatus.AGREEMENT
    assert result.selected.source == "indianapi"
    assert result.selected.value == Decimal("12843")
    assert result.confidence == 1.0


def test_large_difference_is_flagged_and_never_averaged():
    result = resolve_observations([_obs("indianapi", "12843"), _obs("fmp", "15200")])
    assert result.status == ConflictStatus.CONFLICT
    # Primary is selected unchanged -- the average, 14021.5, must never appear.
    assert result.selected.value == Decimal("12843")
    assert result.confidence < 1.0
    assert "differ by" in result.reason


def test_values_are_compared_after_unit_normalization():
    """The same revenue in crore and in plain INR must read as agreement,
    not as a 100-million-fold conflict."""
    result = resolve_observations(
        [_obs("indianapi", "12843"), _obs("fmp", "128430000000", unit=CanonicalUnit.INR)]
    )
    assert result.status == ConflictStatus.AGREEMENT


def test_different_periods_are_not_compared():
    result = resolve_observations([_obs("indianapi", "12843"), _obs("fmp", "9000", period="FY2025")])
    assert result.status == ConflictStatus.INCOMPARABLE
    assert result.selected.source == "indianapi"


def test_no_observations_is_reported_not_crashed():
    result = resolve_observations([])
    assert result.resolution == Resolution.NO_OBSERVATIONS
    assert result.selected is None


# --- Capabilities and registry -----------------------------------------------


def test_screener_does_not_claim_financial_statements():
    """The core honesty rule: Screener has no statement parser, so it must
    never be attempted for the financials category."""
    registry = SourceRegistry(
        chains={Category.FINANCIALS: [SCREENER, INDIANAPI]},
        configured={SCREENER: True, INDIANAPI: True},
    )
    assert not can_serve(registry.capabilities(SCREENER), Category.FINANCIALS)
    assert registry.chain_for(Category.FINANCIALS) == [INDIANAPI]


def test_screener_declares_close_series_not_ohlcv():
    registry = SourceRegistry(chains={}, configured={SCREENER: True})
    capabilities = registry.capabilities(SCREENER)
    assert Capability.DAILY_CLOSE_SERIES in capabilities
    assert Capability.OHLCV not in capabilities


def test_unconfigured_providers_are_dropped_from_the_chain():
    registry = SourceRegistry(
        chains={Category.MARKET_QUOTE: [YFINANCE, FMP]},
        configured={YFINANCE: True, FMP: False},
    )
    assert registry.chain_for(Category.MARKET_QUOTE) == [YFINANCE]
    # ...but the declared chain still reports FMP's intended role.
    assert registry.role_of(FMP, Category.MARKET_QUOTE) == "fallback"
    assert registry.role_of(YFINANCE, Category.MARKET_QUOTE) == "primary"


def test_fmp_limitation_is_recorded_rather_than_reported_as_healthy():
    registry = SourceRegistry(chains={}, configured={FMP: True})
    assert "402" in registry.definition(FMP).limitation
