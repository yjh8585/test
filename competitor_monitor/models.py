"""Record models for collected data.

Each dataclass maps to one SQLite table. Collectors return lists of these
records; the storage layer dispatches on type to upsert them.

Two kinds of records:
  * Snapshots  -> one row per (entity, day). Re-running on the same day updates.
  * Items      -> one row per stable id (media/video). Re-collecting updates metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Instagram
# --------------------------------------------------------------------------- #
@dataclass
class IgProfileSnapshot:
    competitor: str
    username: str
    followers_count: int
    media_count: int
    snapshot_date: str = field(default_factory=_today)
    collected_at: str = field(default_factory=_now)


@dataclass
class IgMedia:
    competitor: str
    media_id: str
    caption: str
    like_count: int
    comments_count: int
    timestamp: str          # ISO8601 from the API
    permalink: str
    collected_at: str = field(default_factory=_now)


# --------------------------------------------------------------------------- #
# YouTube
# --------------------------------------------------------------------------- #
@dataclass
class YtChannelSnapshot:
    competitor: str
    channel_id: str
    subscriber_count: int
    view_count: int
    video_count: int
    snapshot_date: str = field(default_factory=_today)
    collected_at: str = field(default_factory=_now)


@dataclass
class YtVideo:
    competitor: str
    video_id: str
    channel_id: str
    title: str
    published_at: str
    view_count: int
    like_count: int
    comment_count: int
    collected_at: str = field(default_factory=_now)


# --------------------------------------------------------------------------- #
# Naver Search (buzz volume across blog / cafe / news / image)
# --------------------------------------------------------------------------- #
@dataclass
class NaverSearchCount:
    keyword: str
    source: str             # blog | cafearticle | news | image
    total: int              # API-reported total matches
    snapshot_date: str = field(default_factory=_today)
    collected_at: str = field(default_factory=_now)


# --------------------------------------------------------------------------- #
# Naver DataLab (relative search-volume trend; ratio 0-100, NOT absolute)
# --------------------------------------------------------------------------- #
@dataclass
class NaverDataLabPoint:
    keyword_group: str
    period: str             # YYYY-MM-DD bucket from the API
    ratio: float            # relative index 0-100
    collected_at: str = field(default_factory=_now)


# Convenience union used in type hints / docs.
Record = (
    IgProfileSnapshot
    | IgMedia
    | YtChannelSnapshot
    | YtVideo
    | NaverSearchCount
    | NaverDataLabPoint
)
