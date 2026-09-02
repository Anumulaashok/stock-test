"""AI Q&A assistant domain models.

Like the analyst (`app/models/analyst.py`), the Q&A assistant only
interprets already-calculated deterministic results — it answers a
free-form question about a company grounded in `AnalystContext`, and
never issues a buy/sell/hold recommendation or a price-movement
probability. There is deliberately no such field anywhere in this
module; see `app/qa/prompts.py` rules for why.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.analyst import AnalystEvidence


class QAResponse(BaseModel):
    """The assistant's answer to one question, grounded in the same
    evidence namespaces the analyst uses.

    `recommendation_declined` is `True` when the question asked for a
    buy/sell/hold verdict or a price-probability estimate and the
    assistant declined to invent one — the frontend uses this to show a
    short explanatory note next to the answer rather than treating a
    declined verdict as an error.
    """

    answer: str
    evidence: AnalystEvidence = Field(default_factory=AnalystEvidence)
    recommendation_declined: bool = False


class QAErrorCode(StrEnum):
    LLM_UNAVAILABLE = "llm_unavailable"
    TIMEOUT = "timeout"
    EMPTY_RESPONSE = "empty_response"
    MALFORMED_JSON = "malformed_json"
    MISSING_FIELD = "missing_field"
    INVALID_FIELD_TYPE = "invalid_field_type"
    UNEXPECTED_RECOMMENDATION_FIELD = "unexpected_recommendation_field"
    DATA_UNAVAILABLE = "data_unavailable"


class QAError(BaseModel):
    code: QAErrorCode
    message: str


class QAResult(BaseModel):
    """The outcome of one Q&A turn: exactly one of `response`/`error` is set."""

    status: str  # "success" | "error"
    response: QAResponse | None = None
    error: QAError | None = None


class QATickerRequest(BaseModel):
    """Ask a free-form question about a company by ticker.

    The assistant re-derives the same deterministic context
    (`app/analyst/context.py`) the analyst uses — the caller only
    supplies the ticker and the question, never raw numbers.
    """

    ticker: str
    question: str = Field(min_length=1, max_length=1000)
