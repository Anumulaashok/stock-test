"""Research enrichment / market context — external, qualitative evidence.

Provider-agnostic: `base.py` defines `ResearchProvider`, `providers/`
holds concrete HTTP clients + adapters (Finnhub is the first),
`mappers/` holds pure provider-schema-to-domain-model functions,
`processing.py` holds provider-agnostic dedup/freshness/relevance/
ranking, and `service.py` orchestrates retrieval into a structured
`ResearchResult`.

This is NEVER a source of truth for financial metrics, valuation,
scores, or risk severity — those remain the deterministic engines'
exclusive responsibility. Research is optional, additional context for
the AI analyst; its failure never breaks the deterministic pipeline.
"""
