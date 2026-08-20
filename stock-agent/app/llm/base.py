"""LLM provider abstraction.

The rest of the application must depend on this interface, never on a
specific provider's HTTP implementation. This keeps the LLM layer
provider-independent so additional providers (e.g. OpenAI) can be added
later without redesigning callers.

The LLM must never be responsible for deterministic financial
calculations — those belong in the `financial` and `valuation` modules.
"""

from abc import ABC, abstractmethod
from typing import Any


class LLMProviderError(Exception):
    """Raised when an LLM provider fails to produce a response."""


class LLMProvider(ABC):
    """Abstract interface for a text-generation backend."""

    @abstractmethod
    async def generate(
        self, prompt: str, system_prompt: str | None = None, **kwargs: Any
    ) -> str:
        """Generate free-form text for the given prompt.

        `system_prompt`, when given, is sent as a separate system-role
        message ahead of the user prompt — the standard way to separate
        role/instruction framing from task content without inventing a
        second LLM client or a bespoke wire format.
        """
        raise NotImplementedError

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: dict, **kwargs: Any) -> dict:
        """Generate output constrained to the given JSON schema.

        Not required to be fully implemented yet — providers may raise
        NotImplementedError until structured generation is needed.
        """
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider's backend is reachable and healthy."""
        raise NotImplementedError
