"""Alerts API models.

Alerts evaluate on read (D6/D10) -- there is no scheduler, and nothing
here implies background monitoring or push notification. A condition
is only ever checked when a caller invokes `AlertService.evaluate_alerts`,
which the frontend does when a user opens the app/alerts view.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class AlertConditionType(StrEnum):
    PRICE_ABOVE = "PRICE_ABOVE"
    PRICE_BELOW = "PRICE_BELOW"
    SCORE_ABOVE = "SCORE_ABOVE"
    SCORE_BELOW = "SCORE_BELOW"
    DMA_CROSSOVER_GOLDEN = "DMA_CROSSOVER_GOLDEN"
    DMA_CROSSOVER_DEATH = "DMA_CROSSOVER_DEATH"
    REGIME_CHANGE = "REGIME_CHANGE"


# Conditions that compare a live value against a user-supplied number.
THRESHOLD_CONDITIONS = frozenset({
    AlertConditionType.PRICE_ABOVE,
    AlertConditionType.PRICE_BELOW,
    AlertConditionType.SCORE_ABOVE,
    AlertConditionType.SCORE_BELOW,
})


class AlertCreateRequest(BaseModel):
    ticker: str = Field(min_length=1)
    condition_type: AlertConditionType
    threshold_value: Decimal | None = Field(default=None)


class AlertUpdateRequest(BaseModel):
    is_active: bool


class Alert(BaseModel):
    id: str
    ticker: str
    condition_type: AlertConditionType
    threshold_value: Decimal | None
    is_active: bool
    created_at: str
    updated_at: str


class AlertTrigger(BaseModel):
    id: str
    alert_id: str
    ticker: str
    condition_type: AlertConditionType
    triggered_at: str
    observed_value: str
    acknowledged: bool


class AlertEvaluation(BaseModel):
    """One alert's result from a single evaluate-on-read pass. `status`
    is `"met"` / `"not_met"` / `"unavailable"` (the data this condition
    needs -- a quote, a score, DMA history, a regime -- could not be
    read right now); `"unavailable"` is never collapsed into
    `"not_met"`, since those mean different things to a user."""

    alert_id: str
    ticker: str
    condition_type: AlertConditionType
    status: str
    observed_value: str | None
    newly_triggered: bool


class AlertEvaluationResponse(BaseModel):
    checked_at: str
    evaluations: list[AlertEvaluation] = Field(default_factory=list)
