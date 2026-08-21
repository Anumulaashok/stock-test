"""Market-data domain — a separate abstraction from `app.data`
(financial statements). `base.py` defines `MarketDataProvider`,
`providers/` holds concrete clients/adapters (FMP is the first),
`mappers/` holds pure schema mapping, and `service.py` orchestrates
retrieval into a structured `MarketSnapshotResult`. Never used as a
source of truth for financial statements, valuation, scoring, or risk —
those remain `app.data`/`app.financial`/`app.valuation`/`app.scoring`'s
exclusive responsibility.
"""
