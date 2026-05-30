"""Analysis layer for the Competitor Marketing Monitoring System.

Exports:
  build_analysis       – run all metrics in one call, returns a keyed dict.
  summarize_creative   – optional Claude-powered creative theme summary (Korean).

Individual metric functions are also re-exported so callers can pick what they
need without importing the submodules directly.
"""
from __future__ import annotations

from .llm_summary import summarize_creative
from .metrics import (
    build_analysis,
    datalab_trend,
    engagement_rates,
    share_of_voice,
    top_content,
    trend_deltas,
)

__all__ = [
    "build_analysis",
    "summarize_creative",
    "engagement_rates",
    "share_of_voice",
    "trend_deltas",
    "datalab_trend",
    "top_content",
]
