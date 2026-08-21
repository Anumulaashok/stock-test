"""Provider-agnostic research interface.

Mirrors `app.data.base.FinancialDataProvider`'s policy: the rest of the
application depends on this abstraction, never on a concrete provider.
A provider's job is narrow — call its API and map its schema into
`ResearchItem`s. Deduplication, freshness, relevance scoring, and
result-count limiting are deliberately NOT a provider concern; they are
provider-agnostic post-processing owned by `ResearchService` (via
`processing.py`) so every provider benefits from the same rules.
"""

from abc import ABC, abstractmethod

from app.models.research import ResearchItem, ResearchQuery


class ResearchProvider(ABC):
    @abstractmethod
    async def search(self, query: ResearchQuery) -> tuple[list[ResearchItem], list[str]]:
        """Return `(items, warnings)` for `query`, not yet deduplicated,
        scored, or truncated.

        Raises `app.research.exceptions.ResearchProviderError` on failure.
        Never fabricates a title, URL, publisher, or publication date the
        provider didn't actually report.
        """
        raise NotImplementedError
