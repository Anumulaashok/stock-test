"""Internal exception used between a provider client/adapter and
`FinancialDataService`. Never propagates past the service boundary —
`FinancialDataService` catches it and converts it into a
`FinancialDataError` on a `FinancialDataFetchResult`."""

from app.data.models import FinancialDataErrorCode


class ProviderError(Exception):
    def __init__(
        self, code: FinancialDataErrorCode, message: str, retry_after: float | None = None
    ) -> None:
        self.code = code
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)
