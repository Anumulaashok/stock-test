# Blocked

Halt-and-note entries per `docs/AUTONOMY.md` §6 (hard stops). Empty means nothing has hit a hard stop yet.

## Circuit-filter badge ("UPPER CIRCUIT / STRONG BID")

Deprioritized, not infeasible -- deferred at the user's explicit call while the
StockLens visual redesign proceeds with real data only.

NSE publishes per-stock circuit-band limits (`pricebandupper` /
`pricebandlower`); "at upper/lower circuit" would be a real, computed
status (`current_price >= upper_band_limit`, same pattern as
`sectorHeatBand`), not a fabricated one. But none of the current
providers (Screener, yfinance, IndianAPI, FMP) expose that field --
it isn't in the quote model at all.

**Proposed unblock:** a new market-data provider adapter behind
`app/market/providers/` wrapping `nsepython` (or a direct NSE quote
API), adding `upper_circuit_limit` / `lower_circuit_limit` to the
quote model with the usual provenance/freshness wiring. `nsepython` is
an unofficial scraper of NSE's public endpoints -- expect fragility
(no SLA, possible header/cookie rotation, rate limits) that needs the
same `SourceStatus` degraded-state handling every other provider gets.

## Data-quality / audit score ("94.2%", "96.4% [TRACEABLE]")

Deprioritized, not infeasible -- no formula has been designed yet, and
this project's algorithm-proposal rule (CLAUDE.md) requires proposing
2-3 candidate approaches with complexity/tradeoffs before implementing
any new scoring routine, not shipping a percentage that merely looks
plausible.

**Proposed unblock (candidate, not decided):** something like `% of
report fields whose backing source carries SourceStatus in
{"live","verified"}`, using the source-provenance tracking that
already exists (`app/sources/provenance.py`) -- would need a concrete
field-weighting scheme agreed on before implementation, per the
algorithm-proposal rule.

## Market-wide regime / breadth / VIX (dashboard "REGIME: RISK-ON / TRENDING")

Deprioritized, not infeasible. `app/forecasting/ml/regime.py` already
classifies regime, but only **per-ticker** from that ticker's own
price/technical features -- there's no market-wide breadth ratio,
India VIX, or factor-dispersion input anywhere in the app. The same
`nsepython`-based provider proposed above is the concrete path to a
real advance/decline snapshot and index history if this gets
prioritized later.

## Groww brokerage integration (auto-synced real portfolio holdings)

Deprioritized, not infeasible -- deferred at the user's explicit call.

Today `Portfolio` is manually entered (ticker/quantity/avg cost via
`AddHoldingForm`) -- real data, just hand-maintained. The user has
access to a Groww MCP connector in-session (`claude_ai_GrowwMCP`) that
can pull their actual brokerage holdings; a one-off session-side pull
into the existing manual "Add holding" flow is trivial and was offered,
but that only seeds this one user's data for this one session, not a
lasting product feature.

**Proposed unblock (candidate, not decided):** a real Groww brokerage
adapter as a first-class backend feature -- OAuth token storage per
user (new DB table + encryption-at-rest, not a plaintext credential
column), a new provider adapter behind `app/portfolio/` or
`app/market/providers/`, and a sync job to keep holdings current
automatically for any user who connects their account. Comparable in
scope to the `nsepython` integration above -- security-sensitive
(brokerage credentials/tokens) and needs its own design pass, not
something to fold into the current styling work.
