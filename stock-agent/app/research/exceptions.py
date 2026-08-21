"""Internal exception between a research provider and `ResearchService`.
Never propagates past the service boundary — mirrors
`app.data.exceptions.ProviderError`."""

from app.models.research import ResearchErrorCode


class ResearchProviderError(Exception):
    def __init__(
        self, code: ResearchErrorCode, message: str, retry_after: float | None = None
    ) -> None:
        self.code = code
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)
