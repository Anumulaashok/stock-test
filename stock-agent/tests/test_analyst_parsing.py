import json

import pytest

from app.analyst.parsing import AnalystValidationError, build_analyst_response, extract_json_object
from app.models.analyst import AnalystErrorCode

VALID_EVIDENCE = {
    "financial": {"roe", "net_margin", "profitability"},
    "valuation": {"dcf"},
    "risk": {"high_debt_to_equity"},
    "research": {"research_001"},
}


def _evidence(financial=None, valuation=None, risk=None, research=None):
    return {
        "financial": financial or [], "valuation": valuation or [],
        "risk": risk or [], "research": research or [],
    }


def _section(text="ok", financial=None, valuation=None, risk=None, research=None):
    return {"text": text, "evidence": _evidence(financial, valuation, risk, research)}


def _valid_payload(**overrides):
    payload = {
        "investment_thesis": _section("thesis", financial=["roe"]),
        "strengths": ["strong ROE"],
        "weaknesses": ["high leverage"],
        "profitability_analysis": _section("profitable", financial=["roe", "net_margin"]),
        "growth_analysis": _section("growth"),
        "financial_health_analysis": _section("health"),
        "cash_flow_analysis": _section("cash"),
        "valuation_analysis": _section("valuation", valuation=["dcf"]),
        "risk_analysis": _section("risk", risk=["high_debt_to_equity"], research=["research_001"]),
        "key_takeaways": ["takeaway one"],
        "caveats": ["caveat one"],
    }
    payload.update(overrides)
    return payload


# --- extract_json_object -----------------------------------------------------------


def test_extract_json_object_plain():
    data = extract_json_object(json.dumps({"a": 1}))
    assert data == {"a": 1}


def test_extract_json_object_strips_markdown_fence():
    raw = "```json\n" + json.dumps({"a": 1}) + "\n```"
    data = extract_json_object(raw)
    assert data == {"a": 1}


def test_extract_json_object_empty_response():
    with pytest.raises(AnalystValidationError) as exc_info:
        extract_json_object("")
    assert exc_info.value.code is AnalystErrorCode.EMPTY_RESPONSE


def test_extract_json_object_malformed_json():
    with pytest.raises(AnalystValidationError) as exc_info:
        extract_json_object("{not valid json")
    assert exc_info.value.code is AnalystErrorCode.MALFORMED_JSON


def test_extract_json_object_non_object_json():
    with pytest.raises(AnalystValidationError) as exc_info:
        extract_json_object("[1, 2, 3]")
    assert exc_info.value.code is AnalystErrorCode.MALFORMED_JSON


# --- build_analyst_response ---------------------------------------------------------


def test_build_analyst_response_valid():
    response = build_analyst_response(_valid_payload(), "Acme Corp", VALID_EVIDENCE)
    assert response.company_name == "Acme Corp"
    assert response.investment_thesis.text == "thesis"
    assert response.investment_thesis.evidence.financial == ["roe"]
    assert response.strengths == ["strong ROE"]


def test_build_analyst_response_research_evidence_preserved():
    response = build_analyst_response(_valid_payload(), "Acme Corp", VALID_EVIDENCE)
    assert response.risk_analysis.evidence.risk == ["high_debt_to_equity"]
    assert response.risk_analysis.evidence.research == ["research_001"]


def test_build_analyst_response_missing_required_field():
    payload = _valid_payload()
    del payload["risk_analysis"]
    with pytest.raises(AnalystValidationError) as exc_info:
        build_analyst_response(payload, "Acme Corp", VALID_EVIDENCE)
    assert exc_info.value.code is AnalystErrorCode.MISSING_FIELD
    assert "risk_analysis" in exc_info.value.message


def test_build_analyst_response_rejects_recommendation_field():
    payload = _valid_payload(recommendation="BUY")
    with pytest.raises(AnalystValidationError) as exc_info:
        build_analyst_response(payload, "Acme Corp", VALID_EVIDENCE)
    assert exc_info.value.code is AnalystErrorCode.UNEXPECTED_RECOMMENDATION_FIELD


def test_build_analyst_response_rejects_hold_field_case_insensitive():
    payload = _valid_payload(HOLD="yes")
    with pytest.raises(AnalystValidationError) as exc_info:
        build_analyst_response(payload, "Acme Corp", VALID_EVIDENCE)
    assert exc_info.value.code is AnalystErrorCode.UNEXPECTED_RECOMMENDATION_FIELD


def test_build_analyst_response_invalid_section_type():
    payload = _valid_payload(profitability_analysis="just a string, not an object")
    with pytest.raises(AnalystValidationError) as exc_info:
        build_analyst_response(payload, "Acme Corp", VALID_EVIDENCE)
    assert exc_info.value.code is AnalystErrorCode.INVALID_FIELD_TYPE


def test_build_analyst_response_invalid_list_field_type():
    payload = _valid_payload(strengths="not a list")
    with pytest.raises(AnalystValidationError) as exc_info:
        build_analyst_response(payload, "Acme Corp", VALID_EVIDENCE)
    assert exc_info.value.code is AnalystErrorCode.INVALID_FIELD_TYPE


def test_build_analyst_response_evidence_not_an_object_is_invalid():
    payload = _valid_payload(profitability_analysis={"text": "x", "evidence": ["roe"]})
    with pytest.raises(AnalystValidationError) as exc_info:
        build_analyst_response(payload, "Acme Corp", VALID_EVIDENCE)
    assert exc_info.value.code is AnalystErrorCode.INVALID_FIELD_TYPE


def test_build_analyst_response_evidence_namespace_wrong_type_is_invalid():
    payload = _valid_payload(
        profitability_analysis={"text": "x", "evidence": {"financial": "not-a-list"}}
    )
    with pytest.raises(AnalystValidationError) as exc_info:
        build_analyst_response(payload, "Acme Corp", VALID_EVIDENCE)
    assert exc_info.value.code is AnalystErrorCode.INVALID_FIELD_TYPE


def test_build_analyst_response_filters_unknown_evidence_reference():
    payload = _valid_payload(
        profitability_analysis=_section("profitable", financial=["roe", "totally_made_up_metric"])
    )
    response = build_analyst_response(payload, "Acme Corp", VALID_EVIDENCE)
    assert response.profitability_analysis.evidence.financial == ["roe"]
    assert "totally_made_up_metric" not in response.profitability_analysis.evidence.financial


def test_build_analyst_response_filters_unknown_research_reference():
    payload = _valid_payload(
        risk_analysis=_section("risk", risk=["high_debt_to_equity"], research=["research_999"])
    )
    response = build_analyst_response(payload, "Acme Corp", VALID_EVIDENCE)
    assert response.risk_analysis.evidence.research == []


def test_build_analyst_response_evidence_cannot_cross_namespaces():
    # A valuation method name cited under "financial" is not valid there,
    # even though it's a real name somewhere in the context.
    payload = _valid_payload(
        profitability_analysis=_section("profitable", financial=["dcf"])
    )
    response = build_analyst_response(payload, "Acme Corp", VALID_EVIDENCE)
    assert response.profitability_analysis.evidence.financial == []


def test_build_analyst_response_empty_section_text_is_allowed():
    payload = _valid_payload(cash_flow_analysis=_section(text=""))
    response = build_analyst_response(payload, "Acme Corp", VALID_EVIDENCE)
    assert response.cash_flow_analysis.text == ""
