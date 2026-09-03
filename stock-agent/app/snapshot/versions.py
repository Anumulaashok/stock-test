"""Centralized version identifiers stamped onto every `ResearchRunRow`
(and its child snapshot rows).

These are NOT the same as the app's release version -- each identifies
one *methodology*, independently, so old snapshots keep identifying
which methodology produced them even after that methodology changes:

- `DATA_VERSION` -- the shape/meaning of the raw provider payloads this
  app stores (bump if a provider mapper's output shape changes in a way
  that would make an old raw snapshot misleading to re-read).
- `CALCULATION_VERSION` -- `app/financial/`, `app/valuation/`,
  `app/scoring/` (deterministic analysis).
- `FORECAST_VERSION` -- `app/forecasting/` (daily/weekly/monthly
  methodology).
- `PROMPT_VERSION` -- `app/analyst/prompts.py`'s system/user prompt
  shape. Bump this whenever the prompt changes meaningfully enough that
  an old LLM response shouldn't be treated as equivalent to a new one
  for reuse purposes (see `app/snapshot/hashing.py`).

`MODEL_VERSION` is deliberately NOT a constant here -- it's whatever
LLM model is actually configured (`Settings.local_llm_model`) at run
time, since that's what genuinely varies and is what determines whether
an old LLM response is still representative of the current model.

Bump the relevant constant by hand when its methodology changes. Old
`ResearchRunRow`s keep reporting whatever version was current when they
were created -- this module only ever affects new runs.
"""

DATA_VERSION = "v1"
CALCULATION_VERSION = "v1"
FORECAST_VERSION = "v1"
PROMPT_VERSION = "v1"
