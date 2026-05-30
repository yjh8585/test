"""Collector interface — the contract every data source implements.

A Collector turns config + secrets into a flat list of record dataclasses
(from competitor_monitor.models). It does NOT touch storage; the orchestrator
(cli) persists whatever is returned. This keeps sources independent and
testable, and makes adding a new source a matter of writing one subclass.

Contract:
  * ``is_available()`` -> True only if the required secrets are present.
  * ``collect(competitors)`` -> list[Record]. Must NOT raise on a single
    bad/unavailable competitor; log and continue (network is flaky, APIs
    change). Raise only on programmer error.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..config import CompetitorConfig, Secrets, Settings

log = logging.getLogger(__name__)


class CollectorError(RuntimeError):
    """Raised for unrecoverable configuration problems (not per-item failures)."""


class Collector(ABC):
    #: short stable id, e.g. "instagram", "youtube", "naver_search"
    name: str = "base"

    def __init__(self, settings: Settings, secrets: Secrets) -> None:
        self.settings = settings
        self.secrets = secrets

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the required API credentials are configured."""

    @abstractmethod
    def collect(self, competitors: list[CompetitorConfig]) -> list[object]:
        """Collect records for the given competitors. Returns record dataclasses."""

    # Shared helper so every collector logs unavailability the same way.
    def skip_reason(self) -> str | None:
        if not self.is_available():
            return f"[{self.name}] skipped: required API credentials missing (see docs/API_KEYS.md)"
        return None
