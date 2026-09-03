"""Stable hashing of the AI analyst's inputs, for LLM-call reuse.

`compute_input_hash` must produce the SAME hash for the SAME analysis
content, even though several of the input models carry a fetch
timestamp that changes on every provider call (e.g.
`ResearchResult.retrieved_at`). If it didn't, the hash would change on
every research run regardless of whether anything the analyst actually
reasons over changed -- which would silently defeat the entire point of
this module (never re-call the LLM for equivalent input).
"""

import hashlib
import json

# Field names that record *when data was fetched*, not what was fetched --
# volatile across otherwise-identical runs, so always stripped before
# hashing. Kept as one list (not per-model) since `model_dump(mode="json")`
# output is walked generically, and it's harmless for a name to not
# appear in a given model.
_VOLATILE_KEYS = frozenset({"retrieved_at", "data_timestamp", "market_timestamp", "fetched_at", "generated_at"})


def _strip_volatile(value):
    if isinstance(value, dict):
        return {k: _strip_volatile(v) for k, v in value.items() if k not in _VOLATILE_KEYS}
    if isinstance(value, list):
        return [_strip_volatile(v) for v in value]
    return value


def compute_input_hash(
    *,
    financial_analysis: dict,
    valuation: dict | None,
    scoring: dict,
    research: dict | None,
    prompt_version: str,
    model: str,
) -> str:
    """`*_dict` args are each `model_dump(mode="json")` of the same
    objects `AnalystService.analyze` is about to be given -- pass the
    dict form (not the model) so this module has no Pydantic-version
    coupling of its own.
    """
    payload = {
        "financial_analysis": _strip_volatile(financial_analysis),
        "valuation": _strip_volatile(valuation),
        "scoring": _strip_volatile(scoring),
        "research": _strip_volatile(research),
        "prompt_version": prompt_version,
        "model": model,
    }
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
