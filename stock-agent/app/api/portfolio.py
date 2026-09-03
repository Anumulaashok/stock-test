"""Thin transport layer for the portfolio + watchlist APIs.

Every route depends on `get_current_user` — there is no route in this
module reachable without a valid bearer token, and every `PortfolioService`
call is scoped to `current_user.id`, so a request can never touch another
user's data (see the cross-user tests in `tests/test_portfolio_api.py`).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import build_data_source_manager
from app.auth.dependencies import get_current_user
from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import UserRow
from app.models.portfolio import (
    Holding,
    HoldingCreateRequest,
    HoldingUpdateRequest,
    PortfolioSummary,
    WatchlistCreateRequest,
    WatchlistItem,
)
from app.portfolio.service import PortfolioError, PortfolioService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["portfolio"])


def get_portfolio_service(
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> PortfolioService:
    """Uses the same `DataSourceManager` every other caller does, so a
    watchlist price falls back exactly like a research price -- one
    source-selection system, not two. A quote-only call, never a full
    research run.

    Returns a manager even when no provider is configured: `get_quote`
    then reports a structured error and `PortfolioService` marks the
    holding `price_status="unavailable"` rather than failing the request."""
    return PortfolioService(build_data_source_manager(settings, db))


def _error_status(code: str) -> int:
    if code in ("holding_not_found", "watchlist_item_not_found"):
        return status.HTTP_404_NOT_FOUND
    return status.HTTP_409_CONFLICT


@router.get("/portfolio")
async def get_portfolio(
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: PortfolioService = Depends(get_portfolio_service),
) -> list[Holding]:
    return await service.list_holdings(db, current_user.id)


@router.post("/portfolio/holdings", status_code=status.HTTP_201_CREATED)
async def add_holding(
    request: HoldingCreateRequest,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: PortfolioService = Depends(get_portfolio_service),
) -> Holding:
    try:
        return await service.add_holding(db, current_user.id, request)
    except PortfolioError as exc:
        raise HTTPException(status_code=_error_status(exc.code), detail=exc.message) from exc


@router.patch("/portfolio/holdings/{holding_id}")
async def update_holding(
    holding_id: str,
    request: HoldingUpdateRequest,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: PortfolioService = Depends(get_portfolio_service),
) -> Holding:
    try:
        return await service.update_holding(db, current_user.id, holding_id, request)
    except PortfolioError as exc:
        raise HTTPException(status_code=_error_status(exc.code), detail=exc.message) from exc


@router.delete("/portfolio/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(
    holding_id: str,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: PortfolioService = Depends(get_portfolio_service),
) -> None:
    try:
        await service.delete_holding(db, current_user.id, holding_id)
    except PortfolioError as exc:
        raise HTTPException(status_code=_error_status(exc.code), detail=exc.message) from exc


@router.get("/portfolio/summary")
async def get_portfolio_summary(
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioSummary:
    return await service.get_summary(db, current_user.id)


@router.get("/watchlist")
async def get_watchlist(
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: PortfolioService = Depends(get_portfolio_service),
) -> list[WatchlistItem]:
    return await service.list_watchlist(db, current_user.id)


@router.post("/watchlist", status_code=status.HTTP_201_CREATED)
async def add_watchlist_item(
    request: WatchlistCreateRequest,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: PortfolioService = Depends(get_portfolio_service),
) -> WatchlistItem:
    try:
        return await service.add_to_watchlist(db, current_user.id, request.ticker)
    except PortfolioError as exc:
        raise HTTPException(status_code=_error_status(exc.code), detail=exc.message) from exc


@router.delete("/watchlist/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_item(
    ticker: str,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: PortfolioService = Depends(get_portfolio_service),
) -> None:
    try:
        await service.remove_from_watchlist(db, current_user.id, ticker)
    except PortfolioError as exc:
        raise HTTPException(status_code=_error_status(exc.code), detail=exc.message) from exc
