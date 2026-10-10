"""BaseCollector — every adapter subclasses this. The contract:

1. `collect(origin, dest, departure_date)` returns a list[FareQuote].
2. Adapters never write storage or bypass PolicyEngine — the runner owns both.
3. Raw responses go through `self.archive()` before parsing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from .models import FareQuote, SourceTier
from .policy import PolicyEngine
from .storage import archive_raw


class BaseCollector(ABC):
    name: str = "base"
    tier: SourceTier

    def __init__(self, policy: PolicyEngine) -> None:
        self.policy = policy

    def archive(self, payload: str | bytes, label: str) -> str:
        return archive_raw(self.name, payload, label)

    @abstractmethod
    async def collect(self, origin: str, dest: str, departure_date: date) -> list[FareQuote]:
        """Fetch fares for one route+date. Must call policy.allowed() before any hit."""

    async def aclose(self) -> None:
        """Release adapter resources (browser sessions etc.). Runner calls this once."""
