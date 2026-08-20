"""Prompt construction for the AI analyst.

Deliberately three separate, independently testable pieces rather than
one uncontrolled string:

- `build_system_instructions()` — the analyst's fixed role and rules.
- `build_context_section()` — the structured, deterministic data.
- `build_task_section()` — the exact output schema and task framing.

`build_system_instructions` is sent as a system-role message (see the
`system_prompt` parameter added to `LLMProvider.generate`); the context
and task sections are joined into the user-role message.
"""

from app.models.analyst import AnalystContext

_RESPONSE_SCHEMA_DESCRIPTION = """\
Respond with ONLY a single valid JSON object — no markdown code fences, \
no text before or after it. It must have exactly these top-level keys:

{
  "investment_thesis": {"text": "<2-4 sentence summary>", "evidence": ["<name>", ...]},
  "strengths": ["<short factual statement>", ...],
  "weaknesses": ["<short factual statement>", ...],
  "profitability_analysis": {"text": "<1-3 sentences>", "evidence": ["<name>", ...]},
  "growth_analysis": {"text": "<1-3 sentences>", "evidence": ["<name>", ...]},
  "financial_health_analysis": {"text": "<1-3 sentences>", "evidence": ["<name>", ...]},
  "cash_flow_analysis": {"text": "<1-3 sentences>", "evidence": ["<name>", ...]},
  "valuation_analysis": {"text": "<1-3 sentences>", "evidence": ["<name>", ...]},
  "risk_analysis": {"text": "<1-3 sentences>", "evidence": ["<name>", ...]},
  "key_takeaways": ["<short statement>", ...],
  "caveats": ["<short statement>", ...]
}

Each "evidence" array must only contain metric/category/risk names taken \
verbatim from the "name" or "category" or "method" fields in the supplied \
context below — never invent a name that is not present there. If a \
section has no supporting data available, still return the key with an \
empty "evidence" array and text that explicitly says the information is \
unavailable.

Do NOT include a "recommendation", "rating", "buy", "sell", or "hold" \
field anywhere in the response. This is not part of the schema.\
"""


def build_system_instructions() -> str:
    """The analyst's fixed role, scope, and data-integrity rules."""
    return """\
You are a financial research analyst producing a structured explanation \
of an already-completed deterministic financial analysis.

You will be given financial metrics, valuation results, category scores, \
and risk indicators that were all calculated by separate deterministic \
software — not by you. Treat every supplied number and status as \
authoritative and final.

Rules you must follow at all times:

1. Use only the data supplied to you in the structured context.
2. Never invent a financial value that was not supplied.
3. Never treat an "unavailable" or "invalid" value as if it were zero.
4. Never fabricate company facts, market conditions, news, or competitor
   or industry comparisons.
5. Never introduce a financial assumption that was not already part of
   the supplied data.
6. Do not perform independent financial calculations — do not compute a
   new ratio, growth rate, valuation, or score yourself.
7. Do not change or restate a supplied score, valuation figure, or risk
   severity as a different number or level.
8. If a value's status is "unavailable" or "invalid", say so explicitly
   instead of describing it as if it were known
   (e.g. "FCF growth is unavailable because the required historical
   data was not provided" — never "FCF growth is 0%").
9. Do not make a buy, sell, or hold recommendation, and do not include
   any field resembling one. You are explaining evidence, not issuing a
   decision.
10. Clearly separate factual observations (what the data says) from your
    interpretation (what the relationship between data points suggests).
11. You may describe how supplied valuation methods compare to each
    other and to the current price, but never average them into a new
    number, and never invent a target price.
12. Be concise, neutral, and evidence-based. Avoid hype, sensational
    language, guaranteed outcomes, or vague claims not tied to the
    supplied data.
"""


def build_context_section(context: AnalystContext) -> str:
    """The structured, deterministic data, as compact JSON."""
    return (
        "## Structured Financial Context\n\n"
        "This is the complete set of deterministic data available. "
        "Nothing outside this JSON exists for the purpose of this analysis.\n\n"
        f"{context.model_dump_json(exclude_none=True)}"
    )


def build_task_section() -> str:
    """The exact output schema and task framing."""
    return "## Analysis Task\n\n" + _RESPONSE_SCHEMA_DESCRIPTION


def build_user_prompt(context: AnalystContext) -> str:
    """The full user-role message: context, then the task."""
    return f"{build_context_section(context)}\n\n{build_task_section()}"
