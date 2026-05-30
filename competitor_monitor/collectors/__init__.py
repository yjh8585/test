"""Data source collectors.

Each collector subclasses ``Collector`` and returns record dataclasses.
``build_collectors`` wires up every available source for the orchestrator.
"""
from __future__ import annotations

from ..config import Secrets, Settings
from .base import Collector, CollectorError
from .instagram import InstagramCollector
from .naver_datalab import NaverDataLabCollector
from .naver_search import NaverSearchCollector
from .youtube import YouTubeCollector

ALL_COLLECTORS: list[type[Collector]] = [
    InstagramCollector,
    YouTubeCollector,
    NaverSearchCollector,
    NaverDataLabCollector,
]


def build_collectors(settings: Settings, secrets: Secrets) -> list[Collector]:
    return [cls(settings, secrets) for cls in ALL_COLLECTORS]


__all__ = [
    "Collector",
    "CollectorError",
    "InstagramCollector",
    "YouTubeCollector",
    "NaverSearchCollector",
    "NaverDataLabCollector",
    "build_collectors",
    "ALL_COLLECTORS",
]
