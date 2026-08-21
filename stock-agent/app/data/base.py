"""Provider-agnostic data-ingestion interface.

The rest of the application depends on this abstraction, never on a
concrete provider — the same policy Step 1 established for
`LLMProvider`. A second provider (e.g. a different data vendor) can
implement this interface later without changing `FinancialDataService`
or anything downstream of it.
"""

from abc import ABC, abstractmethod

from app.data.models import CompanyIdentifier, FinancialDataResult


class FinancialDataProvider(ABC):
    """Fetches and normalizes one company's financial statements."""

    @abstractmethod
    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataResult:
        """Return normalized data for `identifier`.

        Raises `app.data.exceptions.ProviderError` on any failure
        (network, auth, not-found, malformed/mismatched schema, ...).
        Never fabricates a value that the provider didn't actually report.
        """
        raise NotImplementedError
