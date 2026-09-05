"""Thin transport layer for the Alerts API.

Every route depends on `get_current_user` -- there is no route in this
module reachable without a valid bearer token, and every `AlertService`
call is scoped to `current_user.id`, so a request can never touch
another user's data. `POST /alerts/evaluate` is the only place a
condition is actually checked (D6/D10): there is no scheduler, and this
endpoint must never be described to a caller as anything other than
"check now."
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.service import AlertError, AlertService
from app.api.dependencies import build_data_source_manager
from app.auth.dependencies import get_current_user
from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import UserRow
from app.models.alerts import (
    Alert,
    AlertCreateRequest,
    AlertEvaluationResponse,
    AlertTrigger,
    AlertUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def get_alert_service(
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> AlertService:
    """Same `DataSourceManager` every other quote-consuming caller uses
    (see `app.api.portfolio.get_portfolio_service`) -- one source-
    selection system, not two."""
    manager = build_data_source_manager(settings, db)
    return AlertService(manager)


def _error_status(code: str) -> int:
    if code in ("alert_not_found", "trigger_not_found"):
        return status.HTTP_404_NOT_FOUND
    if code == "duplicate_alert":
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


@router.get("")
async def list_alerts(
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AlertService = Depends(get_alert_service),
) -> list[Alert]:
    return await service.list_alerts(db, current_user.id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_alert(
    request: AlertCreateRequest,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AlertService = Depends(get_alert_service),
) -> Alert:
    try:
        return await service.create_alert(db, current_user.id, request)
    except AlertError as exc:
        raise HTTPException(status_code=_error_status(exc.code), detail=exc.message) from exc


@router.patch("/{alert_id}")
async def set_alert_active(
    alert_id: str,
    request: AlertUpdateRequest,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AlertService = Depends(get_alert_service),
) -> Alert:
    try:
        return await service.set_active(db, current_user.id, alert_id, request.is_active)
    except AlertError as exc:
        raise HTTPException(status_code=_error_status(exc.code), detail=exc.message) from exc


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: str,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AlertService = Depends(get_alert_service),
) -> None:
    try:
        await service.delete_alert(db, current_user.id, alert_id)
    except AlertError as exc:
        raise HTTPException(status_code=_error_status(exc.code), detail=exc.message) from exc


@router.post("/evaluate")
async def evaluate_alerts(
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AlertService = Depends(get_alert_service),
) -> AlertEvaluationResponse:
    """Checks every active alert's condition right now, on this request
    -- the only time any alert is ever evaluated. Never invoked by
    anything except a caller explicitly asking."""
    evaluations = await service.evaluate_alerts(db, current_user.id)
    return AlertEvaluationResponse(checked_at=datetime.now(timezone.utc).isoformat(), evaluations=evaluations)


@router.get("/triggers")
async def list_triggers(
    unacknowledged_only: bool = False,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AlertService = Depends(get_alert_service),
) -> list[AlertTrigger]:
    return await service.list_triggers(db, current_user.id, unacknowledged_only=unacknowledged_only)


@router.post("/triggers/{trigger_id}/acknowledge", status_code=status.HTTP_204_NO_CONTENT)
async def acknowledge_trigger(
    trigger_id: str,
    current_user: UserRow = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AlertService = Depends(get_alert_service),
) -> None:
    try:
        await service.acknowledge_trigger(db, current_user.id, trigger_id)
    except AlertError as exc:
        raise HTTPException(status_code=_error_status(exc.code), detail=exc.message) from exc
