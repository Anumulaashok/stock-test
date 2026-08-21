"""External financial data ingestion.

Provider-agnostic: `base.py` defines the `FinancialDataProvider`
interface, `providers/` holds concrete HTTP clients + adapters (FMP is
the first), `mappers/` holds pure provider-schema-to-domain-model
functions, and `service.py` orchestrates retrieval into a structured
`FinancialDataFetchResult`. The provider's field names and error
payloads never leak past this package — everything downstream only
sees `CompanyFinancials` (from `app/models/financial_statements.py`).
"""
