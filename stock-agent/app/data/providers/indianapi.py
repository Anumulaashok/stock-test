"""IndianAPIProvider: implements `FinancialDataProvider` for stock.indianapi.in.

Combines `IndianAPIClient` (HTTP) and `app.data.mappers.indianapi` (schema
mapping) so IndianAPI's field names (`NetIncome`, `TotalDebt`, `Cash`,
...) never leak past this module — everything downstream only sees
`CompanyFinancials`.

Fallback: `/stock`'s own `financials` field is `null` for some tickers
(verified live for HUDCO, 2026-09-03 — every other `/stock` field is
populated normally; this is a per-company data gap on IndianAPI's side,
not a schema change, and not category-wide — other companies in the same
industry return `financials` normally). When that happens, this provider
falls back to `/historical_stats` (balance sheet + cash flow; see
`app.data.mappers.indianapi_historical`) rather than failing the whole
request. `/stock` remains the primary source and is always tried first;
`/historical_stats` is only ever called when `/stock.financials` is
`null`.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from app.data.base import FinancialDataProvider
from app.data.exceptions import ProviderError
from app.data.mappers.indianapi import build_company_financials
from app.data.mappers.indianapi_historical import (
    map_historical_balance_sheets,
    map_historical_cash_flow_statements,
    map_historical_quarter_results,
    map_historical_ratios,
)
from app.data.models import (
    CompanyIdentifier,
    FinancialDataErrorCode,
    FinancialDataMetadata,
    FinancialDataResult,
)
from app.data.providers.indianapi_client import IndianAPIClient
from app.models.financial_statements import CompanyFinancials

logger = logging.getLogger(__name__)


class IndianAPIProvider(FinancialDataProvider):
    def __init__(
        self, client: IndianAPIClient, clock: Callable[[], datetime] | None = None
    ) -> None:
        self._client = client
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataResult:
        ticker = identifier.ticker

        # This provider is name-search based (see IndianAPIClient) — our
        # canonical `ticker` identifier is passed through as the search
        # term; that mapping is entirely internal to this provider.
        raw = await self._client.get_stock(ticker)

        company_name = raw.get("companyName")
        if not isinstance(company_name, str) or not company_name.strip():
            company_name = ticker

        financials_raw = raw.get("financials")
        if isinstance(financials_raw, list):
            company_financials, currency, warnings = build_company_financials(
                company_name=company_name, ticker=ticker, financials_raw=financials_raw
            )
        elif financials_raw is None:
            logger.info(
                "financial_primary_source_unavailable ticker=%s source=indianapi endpoint=/stock field=financials fallback=historical_stats",
                ticker,
            )
            company_financials, currency, warnings = await self._build_from_historical_stats(
                company_name=company_name, ticker=ticker
            )
        else:
            # The field exists but isn't the shape we know how to read at
            # all (e.g. a string/number) -- a genuine structural mismatch,
            # unlike the documented `null` case above.
            raise ProviderError(
                FinancialDataErrorCode.SCHEMA_MISMATCH,
                "financial data provider response's 'financials' field was neither a list nor null",
            )

        if (
            not company_financials.income_statements
            and not company_financials.balance_sheets
            and not company_financials.cash_flow_statements
        ):
            raise ProviderError(
                FinancialDataErrorCode.MISSING_REQUIRED_DATA,
                f"no usable annual statements could be parsed for '{ticker}'",
            )

        metadata = FinancialDataMetadata(
            provider="indianapi",
            source_identifier=ticker,
            retrieved_at=self._clock().isoformat(),
            currency=currency,
            frequency="annual",
            fiscal_periods=company_financials.fiscal_periods,
        )
        return FinancialDataResult(
            company_financials=company_financials, metadata=metadata, warnings=warnings
        )

    async def _build_from_historical_stats(
        self, company_name: str, ticker: str
    ) -> tuple[CompanyFinancials, str, list[str]]:
        """Fetches all four `/historical_stats` views for logging/
        completeness, but only balance sheet + cash flow feed
        `CompanyFinancials` — those are the only ones the existing
        deterministic financial-analysis engine needs (see
        `app.data.mappers.indianapi_historical`'s module docstring for
        why ratios/quarter_results are parsed but not merged in). Any one
        endpoint failing independently doesn't fail the whole fetch —
        whatever's usable is kept.
        """
        warnings: list[str] = []
        balance_sheets: list = []
        cash_flow_statements: list = []
        sources_used: list[str] = []

        try:
            balance_raw = await self._client.get_historical_balance_sheet(ticker)
        except ProviderError as exc:
            logger.warning("historical_stats_fetch_failed ticker=%s stats=balancesheet error=%s", ticker, exc.message)
            warnings.append(f"balance sheet history unavailable: {exc.message}")
        else:
            balance_sheets, bal_warnings = map_historical_balance_sheets(balance_raw)
            warnings.extend(bal_warnings)
            if balance_sheets:
                sources_used.append("balancesheet")

        try:
            cashflow_raw = await self._client.get_historical_cash_flow(ticker)
        except ProviderError as exc:
            logger.warning("historical_stats_fetch_failed ticker=%s stats=cashflow error=%s", ticker, exc.message)
            warnings.append(f"cash flow history unavailable: {exc.message}")
        else:
            cash_flow_statements, cf_warnings = map_historical_cash_flow_statements(cashflow_raw)
            warnings.extend(cf_warnings)
            if cash_flow_statements:
                sources_used.append("cashflow")

        # Fetched for completeness/validation only -- not merged into
        # CompanyFinancials (see module docstring on the mapper). A
        # failure here never affects the overall result.
        for stats_name, fetch, parse in (
            ("ratios", self._client.get_historical_ratios, map_historical_ratios),
            ("quarter_results", self._client.get_historical_quarter_results, map_historical_quarter_results),
        ):
            try:
                raw = await fetch(ticker)
            except ProviderError as exc:
                logger.warning(
                    "historical_stats_fetch_failed ticker=%s stats=%s error=%s", ticker, stats_name, exc.message
                )
                continue
            parsed = parse(raw)
            if parsed:
                sources_used.append(stats_name)

        if sources_used:
            logger.info(
                "financial_historical_fallback_success ticker=%s sources=%s",
                ticker, ",".join(sources_used),
            )

        fiscal_periods = sorted(
            {s.period for s in balance_sheets} | {s.period for s in cash_flow_statements}
        )
        company_financials = CompanyFinancials(
            company_name=company_name,
            ticker=ticker,
            currency="INR",
            fiscal_periods=fiscal_periods,
            income_statements=[],
            balance_sheets=balance_sheets,
            cash_flow_statements=cash_flow_statements,
        )
        return company_financials, "INR", warnings
