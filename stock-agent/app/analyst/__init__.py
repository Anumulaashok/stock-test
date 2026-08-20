"""AI analyst: an interpretation layer over deterministic results.

`context.py` builds a serializable `AnalystContext` from Step 2-4
outputs (no recalculation); `prompts.py` builds the system/user prompts;
`parsing.py` validates the LLM's raw response into a trusted
`AnalystResponse`; `service.py` wires them together through the existing
`LLMProvider` abstraction. The deterministic engines remain the sole
source of truth — this package only explains their output in natural
language, and never emits a buy/sell/hold recommendation.
"""
