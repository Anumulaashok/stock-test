"""Alerts business logic.

Evaluate on read (D6/D10) -- there is no scheduler anywhere in this
codebase. `evaluate_alerts` is the only place a condition is actually
checked, and it is only ever invoked by a request handler when a
caller asks. The frontend must say plainly that alerts are checked
when the app is open; nothing here should ever be described as
background monitoring or push.

Ownership follows `app.portfolio.service`'s pattern exactly: every
query is scoped by the requesting user's id, and a cross-user lookup
returns "not found" rather than leaking another user's row.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AlertRow,
    AlertTriggerRow,
    DailyPriceHistoryRow,
    ForecastPredictionRow,
    ResearchAnalysisSnapshotRow,
    ResearchRunRow,
)
from app.market.service import MarketDataService
from app.models.alerts import (
    THRESHOLD_CONDITIONS,
    Alert,
    AlertConditionType,
    AlertCreateRequest,
    AlertEvaluation,
    AlertTrigger,
)


class AlertError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _to_alert(row: AlertRow) -> Alert:
    return Alert(
        id=row.id, ticker=row.ticker, condition_type=AlertConditionType(row.condition_type),
        threshold_value=row.threshold_value, is_active=row.is_active,
        created_at=row.created_at.isoformat(), updated_at=row.updated_at.isoformat(),
    )


def _to_trigger(row: AlertTriggerRow, *, ticker: str, condition_type: str) -> AlertTrigger:
    return AlertTrigger(
        id=row.id, alert_id=row.alert_id, ticker=ticker, condition_type=AlertConditionType(condition_type),
        triggered_at=row.triggered_at.isoformat(), observed_value=row.observed_value, acknowledged=row.acknowledged,
    )


class AlertService:
    def __init__(self, market_data_service: MarketDataService | None) -> None:
        self._market_data_service = market_data_service

    async def list_alerts(self, db: AsyncSession, user_id: str) -> list[Alert]:
        stmt = select(AlertRow).where(AlertRow.user_id == user_id).order_by(AlertRow.created_at.desc())
        rows = (await db.execute(stmt)).scalars().all()
        return [_to_alert(row) for row in rows]

    async def create_alert(self, db: AsyncSession, user_id: str, request: AlertCreateRequest) -> Alert:
        if request.condition_type in THRESHOLD_CONDITIONS and request.threshold_value is None:
            raise AlertError("threshold_required", f"{request.condition_type.value} requires a threshold value.")

        existing = (
            await db.execute(
                select(AlertRow).where(
                    AlertRow.user_id == user_id,
                    AlertRow.ticker == request.ticker.upper(),
                    AlertRow.condition_type == request.condition_type.value,
                    AlertRow.threshold_value == request.threshold_value,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise AlertError("duplicate_alert", "An identical alert already exists.")

        row = AlertRow(
            user_id=user_id, ticker=request.ticker.upper(), condition_type=request.condition_type.value,
            threshold_value=request.threshold_value,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _to_alert(row)

    async def _get_owned_alert(self, db: AsyncSession, user_id: str, alert_id: str) -> AlertRow | None:
        stmt = select(AlertRow).where(AlertRow.id == alert_id, AlertRow.user_id == user_id)
        return (await db.execute(stmt)).scalar_one_or_none()

    async def set_active(self, db: AsyncSession, user_id: str, alert_id: str, is_active: bool) -> Alert:
        row = await self._get_owned_alert(db, user_id, alert_id)
        if row is None:
            raise AlertError("alert_not_found", "Alert not found.")
        row.is_active = is_active
        await db.commit()
        await db.refresh(row)
        return _to_alert(row)

    async def delete_alert(self, db: AsyncSession, user_id: str, alert_id: str) -> None:
        row = await self._get_owned_alert(db, user_id, alert_id)
        if row is None:
            raise AlertError("alert_not_found", "Alert not found.")
        await db.delete(row)
        await db.commit()

    async def list_triggers(self, db: AsyncSession, user_id: str, *, unacknowledged_only: bool = False) -> list[AlertTrigger]:
        stmt = (
            select(AlertTriggerRow, AlertRow.ticker, AlertRow.condition_type)
            .join(AlertRow, AlertRow.id == AlertTriggerRow.alert_id)
            .where(AlertRow.user_id == user_id)
            .order_by(AlertTriggerRow.triggered_at.desc())
        )
        if unacknowledged_only:
            stmt = stmt.where(AlertTriggerRow.acknowledged.is_(False))
        rows = (await db.execute(stmt)).all()
        return [_to_trigger(trigger, ticker=ticker, condition_type=condition_type) for trigger, ticker, condition_type in rows]

    async def acknowledge_trigger(self, db: AsyncSession, user_id: str, trigger_id: str) -> None:
        stmt = (
            select(AlertTriggerRow)
            .join(AlertRow, AlertRow.id == AlertTriggerRow.alert_id)
            .where(AlertTriggerRow.id == trigger_id, AlertRow.user_id == user_id)
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise AlertError("trigger_not_found", "Alert trigger not found.")
        row.acknowledged = True
        await db.commit()

    # --- Evaluation (the only place a condition is actually checked) ----------------

    async def evaluate_alerts(self, db: AsyncSession, user_id: str) -> list[AlertEvaluation]:
        stmt = select(AlertRow).where(AlertRow.user_id == user_id, AlertRow.is_active.is_(True))
        rows = (await db.execute(stmt)).scalars().all()

        results: list[AlertEvaluation] = []
        for row in rows:
            results.append(await self._evaluate_one(db, row))
        return results

    async def _evaluate_one(self, db: AsyncSession, row: AlertRow) -> AlertEvaluation:
        condition = AlertConditionType(row.condition_type)

        if condition in (AlertConditionType.PRICE_ABOVE, AlertConditionType.PRICE_BELOW):
            value = await self._current_price(row.ticker)
            met = value is not None and (
                (condition is AlertConditionType.PRICE_ABOVE and value > row.threshold_value)
                or (condition is AlertConditionType.PRICE_BELOW and value < row.threshold_value)
            )
            observed = None if value is None else str(value)
        elif condition in (AlertConditionType.SCORE_ABOVE, AlertConditionType.SCORE_BELOW):
            score = await self._latest_score(db, row.ticker)
            met = score is not None and (
                (condition is AlertConditionType.SCORE_ABOVE and score > row.threshold_value)
                or (condition is AlertConditionType.SCORE_BELOW and score < row.threshold_value)
            )
            observed = None if score is None else str(score)
        elif condition in (AlertConditionType.DMA_CROSSOVER_GOLDEN, AlertConditionType.DMA_CROSSOVER_DEATH):
            signal = await self._latest_crossover_signal(db, row.ticker)
            met = signal is not None and (
                (condition is AlertConditionType.DMA_CROSSOVER_GOLDEN and signal == "golden_cross")
                or (condition is AlertConditionType.DMA_CROSSOVER_DEATH and signal == "death_cross")
            )
            observed = signal
        elif condition is AlertConditionType.REGIME_CHANGE:
            regime = await self._latest_regime(db, row.ticker)
            met = regime is not None and row.last_seen_regime is not None and regime != row.last_seen_regime
            observed = regime
            if regime is not None and regime != row.last_seen_regime:
                row.last_seen_regime = regime
                await db.commit()
        else:
            met = False
            observed = None

        if observed is None:
            status = "unavailable"
        else:
            status = "met" if met else "not_met"

        newly_triggered = False
        if met and observed is not None:
            newly_triggered = await self._record_trigger_if_new(db, row, observed)

        return AlertEvaluation(
            alert_id=row.id, ticker=row.ticker, condition_type=condition, status=status,
            observed_value=observed, newly_triggered=newly_triggered,
        )

    async def _record_trigger_if_new(self, db: AsyncSession, row: AlertRow, observed_value: str) -> bool:
        """Avoids re-triggering on every read while the condition stays
        met -- a trigger is only recorded when the most recent one (if
        any) reported a different observed value, or there is none yet."""
        latest = (
            await db.execute(
                select(AlertTriggerRow)
                .where(AlertTriggerRow.alert_id == row.id)
                .order_by(AlertTriggerRow.triggered_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest is not None and latest.observed_value == observed_value:
            return False
        db.add(AlertTriggerRow(alert_id=row.id, observed_value=observed_value))
        await db.commit()
        return True

    async def _current_price(self, ticker: str) -> Decimal | None:
        if self._market_data_service is None:
            return None
        result = await self._market_data_service.get_quote(ticker)
        if result.status == "success" and result.snapshot and result.snapshot.quote:
            return result.snapshot.quote.current_price
        return None

    async def _latest_score(self, db: AsyncSession, ticker: str) -> Decimal | None:
        stmt = (
            select(ResearchAnalysisSnapshotRow.scoring_json)
            .join(ResearchRunRow, ResearchAnalysisSnapshotRow.research_run_id == ResearchRunRow.id)
            .where(ResearchRunRow.ticker == ticker, ResearchRunRow.status.in_(["COMPLETED", "PARTIAL"]))
            .order_by(ResearchRunRow.completed_at.desc())
            .limit(1)
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if not row:
            return None
        try:
            scoring = json.loads(row)
        except json.JSONDecodeError:
            return None
        overall_score = scoring.get("overall_score")
        return Decimal(str(overall_score)) if overall_score is not None else None

    async def _latest_crossover_signal(self, db: AsyncSession, ticker: str) -> str | None:
        stmt = (
            select(DailyPriceHistoryRow.dma50, DailyPriceHistoryRow.dma200)
            .where(DailyPriceHistoryRow.ticker == ticker, DailyPriceHistoryRow.dma50.is_not(None), DailyPriceHistoryRow.dma200.is_not(None))
            .order_by(DailyPriceHistoryRow.date.desc())
            .limit(1)
        )
        row = (await db.execute(stmt)).first()
        if row is None:
            return None
        dma50, dma200 = row
        if dma50 > dma200:
            return "golden_cross"
        if dma50 < dma200:
            return "death_cross"
        return "neutral"

    async def _latest_regime(self, db: AsyncSession, ticker: str) -> str | None:
        stmt = (
            select(ForecastPredictionRow.regime)
            .where(ForecastPredictionRow.ticker == ticker, ForecastPredictionRow.regime.is_not(None))
            .order_by(ForecastPredictionRow.prediction_timestamp.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()
