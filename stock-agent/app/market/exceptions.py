"""Internal exception between a market-data provider and `MarketDataService`.
Never propagates past the service boundary — mirrors
`app.data.exceptions.ProviderError` / `app.research.exceptions.ResearchProviderError`.
"""

from app.models.market import MarketDataErrorCode


class MarketProviderError(Exception):
    def __init__(
        self, code: MarketDataErrorCode, message: str, retry_after: float | None = None
    ) -> None:
        self.code = code
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)
