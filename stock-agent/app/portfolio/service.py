"""Portfolio/watchlist business logic.

Ownership is enforced here, in every query — every method is scoped by
the requesting user's id, and a cross-user lookup returns "not found"
rather than leaking whether the resource exists under another user.
There is no code path that can return another user's data (see the
explicit cross-user tests in `tests/test_portfolio_api.py`).

Prices are never stored: `market_value`/`unrealized_gain*` are computed
here, at request time, from `quantity`/`average_cost` plus a live
`MarketQuote`. An unavailable price yields `None`, never `0` — the
portfolio total then reflects only the holdings that *do* have a price,
with a warning explaining why, rather than silently understating value.
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HoldingRow, PortfolioRow, WatchlistItemRow
from app.market.service import MarketDataService
from app.models.portfolio import (
    Holding,
    HoldingCreateRequest,
    HoldingUpdateRequest,
    HoldingWithMarketData,
    PortfolioSummary,
    WatchlistItem,
)

_CENTS = Decimal("0.01")


class PortfolioError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _to_holding(row: HoldingRow) -> Holding:
    return Holding(
        id=row.id, ticker=row.ticker, quantity=row.quantity, average_cost=row.average_cost,
        added_at=row.added_at.isoformat(), updated_at=row.updated_at.isoformat(),
    )


class PortfolioService:
    def __init__(self, market_data_service: MarketDataService | None) -> None:
        self._market_data_service = market_data_service

    async def _get_or_create_portfolio(self, db: AsyncSession, user_id: str) -> PortfolioRow:
        portfolio = await db.scalar(select(PortfolioRow).where(PortfolioRow.user_id == user_id))
        if portfolio is None:
            portfolio = PortfolioRow(user_id=user_id, name="My Portfolio")
            db.add(portfolio)
            await db.commit()
            await db.refresh(portfolio)
        return portfolio

    async def list_holdings(self, db: AsyncSession, user_id: str) -> list[Holding]:
        portfolio = await self._get_or_create_portfolio(db, user_id)
        rows = (
            await db.scalars(select(HoldingRow).where(HoldingRow.portfolio_id == portfolio.id))
        ).all()
        return [_to_holding(row) for row in rows]

    async def add_holding(
        self, db: AsyncSession, user_id: str, request: HoldingCreateRequest
    ) -> Holding:
        portfolio = await self._get_or_create_portfolio(db, user_id)
        ticker = request.ticker.strip().upper()

        existing = await db.scalar(
            select(HoldingRow).where(
                HoldingRow.portfolio_id == portfolio.id, HoldingRow.ticker == ticker
            )
        )
        if existing is not None:
            raise PortfolioError("duplicate_holding", f"A holding for '{ticker}' already exists.")

        row = HoldingRow(
            portfolio_id=portfolio.id, ticker=ticker,
            quantity=request.quantity, average_cost=request.average_cost,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _to_holding(row)

    async def _get_owned_holding(self, db: AsyncSession, user_id: str, holding_id: str) -> HoldingRow:
        portfolio = await self._get_or_create_portfolio(db, user_id)
        row = await db.scalar(
            select(HoldingRow).where(
                HoldingRow.id == holding_id, HoldingRow.portfolio_id == portfolio.id
            )
        )
        if row is None:
            raise PortfolioError("holding_not_found", "Holding not found.")
        return row

    async def update_holding(
        self, db: AsyncSession, user_id: str, holding_id: str, request: HoldingUpdateRequest
    ) -> Holding:
        row = await self._get_owned_holding(db, user_id, holding_id)
        if request.quantity is not None:
            row.quantity = request.quantity
        if request.average_cost is not None:
            row.average_cost = request.average_cost
        await db.commit()
        await db.refresh(row)
        return _to_holding(row)

    async def delete_holding(self, db: AsyncSession, user_id: str, holding_id: str) -> None:
        row = await self._get_owned_holding(db, user_id, holding_id)
        await db.delete(row)
        await db.commit()

    async def get_summary(self, db: AsyncSession, user_id: str) -> PortfolioSummary:
        portfolio = await self._get_or_create_portfolio(db, user_id)
        rows = (
            await db.scalars(select(HoldingRow).where(HoldingRow.portfolio_id == portfolio.id))
        ).all()

        holdings_with_market: list[HoldingWithMarketData] = []
        warnings: list[str] = []
        invested_capital = Decimal(0)
        priced_value_total = Decimal(0)
        all_priced = True

        for row in rows:
            invested_capital += row.quantity * row.average_cost
            current_price, price_status = await self._current_price(row.ticker, warnings)

            if current_price is None:
                all_priced = False
                market_value = unrealized_gain = unrealized_gain_percent = None
            else:
                market_value = (row.quantity * current_price).quantize(_CENTS, rounding=ROUND_HALF_UP)
                cost_basis = row.quantity * row.average_cost
                unrealized_gain = market_value - cost_basis
                unrealized_gain_percent = (
                    (unrealized_gain / cost_basis * 100) if cost_basis != 0 else None
                )
                priced_value_total += market_value

            holdings_with_market.append(
                HoldingWithMarketData(
                    id=row.id, ticker=row.ticker, quantity=row.quantity, average_cost=row.average_cost,
                    added_at=row.added_at.isoformat(), updated_at=row.updated_at.isoformat(),
                    current_price=current_price, price_status=price_status,
                    market_value=market_value, unrealized_gain=unrealized_gain,
                    unrealized_gain_percent=unrealized_gain_percent,
                )
            )

        portfolio_value, unrealized_gain_total, unrealized_gain_percent_total = self._aggregate(
            rows, all_priced, priced_value_total, invested_capital, warnings
        )

        return PortfolioSummary(
            portfolio_id=portfolio.id, invested_capital=invested_capital, portfolio_value=portfolio_value,
            unrealized_gain=unrealized_gain_total, unrealized_gain_percent=unrealized_gain_percent_total,
            holdings=holdings_with_market, warnings=warnings,
        )

    async def _current_price(
        self, ticker: str, warnings: list[str]
    ) -> tuple[Decimal | None, str]:
        if self._market_data_service is None:
            warnings.append(f"current price unavailable for {ticker}: no market data provider configured")
            return None, "unavailable"

        result = await self._market_data_service.get_quote(ticker)
        if result.status == "success" and result.snapshot and result.snapshot.quote:
            quote = result.snapshot.quote
            if quote.current_price is None:
                warnings.append(f"current price unavailable for {ticker}")
            return quote.current_price, quote.freshness.value

        detail = result.error.message if result.error else "unknown error"
        warnings.append(f"current price unavailable for {ticker}: {detail}")
        return None, "unavailable"

    def _aggregate(
        self,
        rows: list[HoldingRow],
        all_priced: bool,
        priced_value_total: Decimal,
        invested_capital: Decimal,
        warnings: list[str],
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        if not rows:
            return Decimal(0), Decimal(0), None
        if all_priced:
            gain = priced_value_total - invested_capital
            gain_percent = (gain / invested_capital * 100) if invested_capital != 0 else None
            return priced_value_total, gain, gain_percent

        warnings.append("portfolio_value reflects only the holdings with an available current price")
        portfolio_value = priced_value_total if priced_value_total > 0 else None
        return portfolio_value, None, None

    # --- Watchlist ----------------------------------------------------------------

    async def list_watchlist(self, db: AsyncSession, user_id: str) -> list[WatchlistItem]:
        rows = (
            await db.scalars(select(WatchlistItemRow).where(WatchlistItemRow.user_id == user_id))
        ).all()
        return [WatchlistItem(ticker=row.ticker, created_at=row.created_at.isoformat()) for row in rows]

    async def add_to_watchlist(self, db: AsyncSession, user_id: str, ticker: str) -> WatchlistItem:
        ticker = ticker.strip().upper()
        existing = await db.scalar(
            select(WatchlistItemRow).where(
                WatchlistItemRow.user_id == user_id, WatchlistItemRow.ticker == ticker
            )
        )
        if existing is not None:
            raise PortfolioError(
                "duplicate_watchlist_item", f"'{ticker}' is already on your watchlist."
            )
        row = WatchlistItemRow(user_id=user_id, ticker=ticker)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return WatchlistItem(ticker=row.ticker, created_at=row.created_at.isoformat())

    async def remove_from_watchlist(self, db: AsyncSession, user_id: str, ticker: str) -> None:
        ticker = ticker.strip().upper()
        row = await db.scalar(
            select(WatchlistItemRow).where(
                WatchlistItemRow.user_id == user_id, WatchlistItemRow.ticker == ticker
            )
        )
        if row is None:
            raise PortfolioError("watchlist_item_not_found", f"'{ticker}' is not on your watchlist.")
        await db.delete(row)
        await db.commit()
