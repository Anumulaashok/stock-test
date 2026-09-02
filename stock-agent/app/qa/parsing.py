"""Parses and validates the LLM's raw text into a trusted `QAResponse`.

Mirrors `app/analyst/parsing.py`'s policy: the raw LLM response is never
trusted directly. It must parse as JSON, contain every required key
with the right type, and any evidence it cites must actually exist in
the `AnalystContext` that was supplied — anything else is rejected
rather than silently patched or invented.
"""

import json

from app.models.analyst import AnalystEvidence
from app.models.qa import QAErrorCode, QAResponse

_EVIDENCE_NAMESPACES = ("financial", "valuation", "risk", "research")
_REQUIRED_FIELDS = ("answer", "evidence")
_FORBIDDEN_KEYS = {"recommendation", "rating", "buy", "sell", "hold", "action", "signal"}


class QAValidationError(Exception):
    """Raised when the LLM's response cannot be trusted as-is."""

    def __init__(self, code: QAErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def extract_json_object(raw_text: str) -> dict:
    """Parse `raw_text` as a JSON object, tolerating markdown code fences."""
    text = raw_text.strip()
    if not text:
        raise QAValidationError(QAErrorCode.EMPTY_RESPONSE, "LLM returned an empty response")

    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1 :] if first_newline != -1 else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise QAValidationError(
            QAErrorCode.MALFORMED_JSON, f"LLM response was not valid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise QAValidationError(QAErrorCode.MALFORMED_JSON, "LLM response JSON was not an object")
    return data


def _validate_evidence(raw: object) -> AnalystEvidence:
    if not isinstance(raw, dict):
        raise QAValidationError(
            QAErrorCode.INVALID_FIELD_TYPE,
            "'evidence' must be an object with financial/valuation/risk/research keys",
        )
    namespaced: dict[str, list[str]] = {}
    for namespace in _EVIDENCE_NAMESPACES:
        values = raw.get(namespace, [])
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise QAValidationError(
                QAErrorCode.INVALID_FIELD_TYPE, f"'evidence.{namespace}' must be a list of strings"
            )
        namespaced[namespace] = values
    return AnalystEvidence(**namespaced)


def _filter_evidence(evidence: AnalystEvidence, valid_evidence: dict[str, set[str]]) -> AnalystEvidence:
    filtered = {
        namespace: [e for e in getattr(evidence, namespace) if e in valid_evidence.get(namespace, set())]
        for namespace in _EVIDENCE_NAMESPACES
    }
    return AnalystEvidence(**filtered)


def build_qa_response(data: dict, valid_evidence: dict[str, set[str]]) -> QAResponse:
    """Validate `data` (already-parsed JSON) and build a trusted `QAResponse`.

    Evidence references that don't match anything in `valid_evidence`
    are silently dropped rather than failing the whole response — a
    stray citation is not the same class of problem as malformed
    structure.
    """
    present_forbidden = _FORBIDDEN_KEYS & {key.lower() for key in data.keys()}
    if present_forbidden:
        raise QAValidationError(
            QAErrorCode.UNEXPECTED_RECOMMENDATION_FIELD,
            f"response contained disallowed field(s): {', '.join(sorted(present_forbidden))}",
        )

    missing = [field for field in _REQUIRED_FIELDS if field not in data]
    if missing:
        raise QAValidationError(
            QAErrorCode.MISSING_FIELD, f"response is missing required field(s): {', '.join(missing)}"
        )

    answer = data["answer"]
    if not isinstance(answer, str):
        raise QAValidationError(QAErrorCode.INVALID_FIELD_TYPE, "'answer' must be a string")

    evidence = _filter_evidence(_validate_evidence(data["evidence"]), valid_evidence)

    recommendation_declined = data.get("recommendation_declined", False)
    if not isinstance(recommendation_declined, bool):
        raise QAValidationError(
            QAErrorCode.INVALID_FIELD_TYPE, "'recommendation_declined' must be a boolean"
        )

    return QAResponse(answer=answer, evidence=evidence, recommendation_declined=recommendation_declined)
