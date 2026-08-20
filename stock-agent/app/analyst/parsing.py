"""Parses and validates the LLM's raw text into a trusted `AnalystResponse`.

The raw LLM response is never trusted directly: it must parse as JSON,
contain every required key with the right type, contain no
recommendation-shaped field, and any evidence it cites must actually
exist in the `AnalystContext` that was supplied — anything else is
rejected rather than silently patched or invented.
"""

import json

from app.models.analyst import AnalystErrorCode, AnalystResponse, AnalystSection

_SECTION_FIELDS = [
    "investment_thesis",
    "profitability_analysis",
    "growth_analysis",
    "financial_health_analysis",
    "cash_flow_analysis",
    "valuation_analysis",
    "risk_analysis",
]
_LIST_FIELDS = ["strengths", "weaknesses", "key_takeaways", "caveats"]
_REQUIRED_FIELDS = _SECTION_FIELDS + _LIST_FIELDS
_FORBIDDEN_KEYS = {"recommendation", "rating", "buy", "sell", "hold", "action", "signal"}


class AnalystValidationError(Exception):
    """Raised when the LLM's response cannot be trusted as-is."""

    def __init__(self, code: AnalystErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def extract_json_object(raw_text: str) -> dict:
    """Parse `raw_text` as a JSON object, tolerating markdown code fences.

    Raises `AnalystValidationError` (MALFORMED_JSON or EMPTY_RESPONSE)
    rather than letting a `json.JSONDecodeError` propagate.
    """
    text = raw_text.strip()
    if not text:
        raise AnalystValidationError(AnalystErrorCode.EMPTY_RESPONSE, "LLM returned an empty response")

    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1 :] if first_newline != -1 else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[: -3]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AnalystValidationError(
            AnalystErrorCode.MALFORMED_JSON, f"LLM response was not valid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise AnalystValidationError(
            AnalystErrorCode.MALFORMED_JSON, "LLM response JSON was not an object"
        )
    return data


def _validate_section(name: str, raw: object) -> AnalystSection:
    if not isinstance(raw, dict):
        raise AnalystValidationError(
            AnalystErrorCode.INVALID_FIELD_TYPE, f"'{name}' must be an object with 'text'/'evidence'"
        )
    text = raw.get("text")
    if not isinstance(text, str):
        raise AnalystValidationError(
            AnalystErrorCode.INVALID_FIELD_TYPE, f"'{name}.text' must be a string"
        )
    evidence = raw.get("evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
        raise AnalystValidationError(
            AnalystErrorCode.INVALID_FIELD_TYPE, f"'{name}.evidence' must be a list of strings"
        )
    return AnalystSection(text=text, evidence=evidence)


def _validate_string_list(name: str, raw: object) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise AnalystValidationError(
            AnalystErrorCode.INVALID_FIELD_TYPE, f"'{name}' must be a list of strings"
        )
    return raw


def _filter_evidence(section: AnalystSection, valid_evidence: set[str]) -> AnalystSection:
    return section.model_copy(update={"evidence": [e for e in section.evidence if e in valid_evidence]})


def build_analyst_response(
    data: dict, company_name: str, valid_evidence: set[str]
) -> AnalystResponse:
    """Validate `data` (already-parsed JSON) and build a trusted `AnalystResponse`.

    Raises `AnalystValidationError` for a missing/mistyped required field
    or an unexpected recommendation-shaped key. Evidence references that
    don't match anything in `valid_evidence` are silently dropped rather
    than failing the whole response — a stray citation is not the same
    class of problem as malformed structure.
    """
    present_forbidden = _FORBIDDEN_KEYS & {key.lower() for key in data.keys()}
    if present_forbidden:
        raise AnalystValidationError(
            AnalystErrorCode.UNEXPECTED_RECOMMENDATION_FIELD,
            f"response contained disallowed field(s): {', '.join(sorted(present_forbidden))}",
        )

    missing = [field for field in _REQUIRED_FIELDS if field not in data]
    if missing:
        raise AnalystValidationError(
            AnalystErrorCode.MISSING_FIELD, f"response is missing required field(s): {', '.join(missing)}"
        )

    sections = {name: _validate_section(name, data[name]) for name in _SECTION_FIELDS}
    sections = {name: _filter_evidence(section, valid_evidence) for name, section in sections.items()}
    lists = {name: _validate_string_list(name, data[name]) for name in _LIST_FIELDS}

    return AnalystResponse(
        company_name=company_name,
        investment_thesis=sections["investment_thesis"],
        strengths=lists["strengths"],
        weaknesses=lists["weaknesses"],
        profitability_analysis=sections["profitability_analysis"],
        growth_analysis=sections["growth_analysis"],
        financial_health_analysis=sections["financial_health_analysis"],
        cash_flow_analysis=sections["cash_flow_analysis"],
        valuation_analysis=sections["valuation_analysis"],
        risk_analysis=sections["risk_analysis"],
        key_takeaways=lists["key_takeaways"],
        caveats=lists["caveats"],
    )
